"""User workflows and chart/layout regressions, using an isolated local store."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from PySide6 import QtCore, QtGui, QtWidgets
from quantdesk.ui import Window
from quantdesk.service import Service
from quantdesk.charts import timestamp
from quantdesk.theme import DARK, LIGHT


def contrast(foreground, background):
    def luminance(hex_value):
        channels=[int(hex_value[i:i+2],16)/255 for i in (1,3,5)]
        linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(c*w for c,w in zip(linear,(.2126,.7152,.0722)))
    a,b=sorted((luminance(foreground),luminance(background)))
    return (b+.05)/(a+.05)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
        QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/consola.ttf')

    def setUp(self):
        self.home=tempfile.TemporaryDirectory()
        self.window=Window(Service(self.home.name))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.home.cleanup()

    def result(self, **settings):
        w=self.window
        return w.service.backtest(w.backtest_data.currentData(),w.definition(),settings)

    def test_startup_and_filter_have_meaningful_context(self):
        w=self.window
        self.assertTrue(w.current_dataset())
        self.assertIn('AAPL',w.data_context.text())
        self.assertTrue(w.data_chart.items())
        w.search.setText('no-matching-symbol')
        self.assertEqual(w.datasets_table.model().rowCount(),0)
        self.assertEqual(w.data_table.model().rowCount(),0)
        self.assertIn('没有匹配',w.data_context.text())
        w.select_dataset(w.service.store.datasets()[0]['id'])
        self.assertEqual(w.search.text(),'')
        self.assertIn('AAPL',w.data_context.text())

    def test_parameter_edits_and_invalid_json_cannot_masquerade_as_current_results(self):
        w=self.window
        w.show_result(self.result())
        w.quick_fields['fast'].setText('5')
        self.assertEqual(w.definition()['fast'],5)
        self.assertEqual(w.strategy_form.fields['fast'].text(),'5')
        self.assertIn('尚未更新',w.result_state.text())
        w.quick_fields['fast'].setText('10')
        self.assertNotIn('尚未更新',w.result_state.text())
        w.strategy_editor.setPlainText('{broken')
        self.assertIn('尚未更新',w.result_state.text())
        w.strategy_editor.setPlainText(json.dumps(w.result['strategy']))
        self.assertNotIn('尚未更新',w.result_state.text())

    def test_loading_restores_config_and_trade_drills_into_correct_date(self):
        w=self.window
        result=self.result(capital=120000,fee_bps=12,allocation_pct=80)
        w.settings['capital'].setText('99999')
        w.show_result(result)
        self.assertEqual(w.current_config(),result['config'])
        self.assertEqual(w.definition(),result['strategy'])
        self.assertNotIn('尚未更新',w.result_state.text())
        w.focus_trade(w.result_tables['trades'].model().index(0,0))
        day=result['trades'][0]['date']
        bounds=w.charts.price.viewRange()[0]
        self.assertAlmostEqual(sum(bounds)/2,timestamp(day))
        self.assertIn(day,w.charts.readout.text())
        self.assertEqual(w.result_tabs.currentIndex(),0)

    def test_small_windows_keep_actions_and_charts_accessible(self):
        w=self.window
        w.show_result(self.result())
        for width,height in [(1280,720),(1060,680)]:
            with self.subTest(size=(width,height)):
                w.resize(width,height)
                self.app.processEvents()
                self.assertEqual(w.width(),width)
                for button in (w.run_button,w.export_button):
                    rect=QtCore.QRect(button.mapTo(w,QtCore.QPoint()),button.size())
                    self.assertTrue(w.rect().contains(rect),rect)
                    self.assertTrue(button.isVisible())
                for control in (w.theme_button,w.status):
                    rect=QtCore.QRect(control.mapTo(w,QtCore.QPoint()),control.size())
                    self.assertTrue(w.rect().contains(rect),(w.rect(),rect))
                bounds=w.charts.rect()
                rectangles=[]
                for chart in (w.charts.price,w.charts.secondary,w.charts.equity,w.charts.drawdown):
                    rect=QtCore.QRect(chart.mapTo(w.charts,QtCore.QPoint()),chart.size())
                    self.assertTrue(bounds.contains(rect),(bounds,rect))
                    self.assertGreaterEqual(chart.height(),80)
                    rectangles.append(rect)
                for i,rect in enumerate(rectangles):
                    for other in rectangles[i+1:]:self.assertFalse(rect.intersects(other))

    def test_different_width_charts_share_exact_dates_in_both_directions(self):
        w=self.window
        w.show_result(self.result())
        self.app.processEvents()
        price=w.charts.price
        for source in (price,w.charts.equity,w.charts.drawdown):
            source.setXRange(timestamp('2016-01-01'),timestamp('2016-09-01'),padding=0)
            self.app.processEvents()
            for chart in (price,w.charts.equity,w.charts.drawdown):
                for a,b in zip(source.viewRange()[0],chart.viewRange()[0]):self.assertAlmostEqual(a,b)
        w.charts.reset_view()
        self.app.processEvents()
        self.assertLess(price.viewRange()[0][0],timestamp(w.result['curve'][0]['date']))
        self.assertGreater(price.viewRange()[0][1],timestamp(w.result['curve'][-1]['date']))

    def test_batch_auto_comparison_and_incompatible_selection_feedback(self):
        w=self.window
        results=w.service.tune(w.backtest_data.currentData(),w.definition(),{}, {'fast':[5,10],'slow':[20,30]})
        w.batch_done(results)
        self.assertEqual(set(w.selected_experiments()),{r['id'] for r in results})
        self.assertEqual(w.comparison_stack.currentIndex(),1)
        self.assertEqual(len(w.comparison.plotItem.listDataItems()),4)
        self.assertTrue(all(r['_curve_color'] for r in w.experiments.model().rows))
        incompatible=self.result(start='2016-01-01')
        w.refresh_experiments()
        w.select_experiments([results[0]['id'],incompatible['id']])
        self.assertEqual(w.comparison_stack.currentIndex(),0)
        self.assertIn('区间不同',w.comparison_hint.text())
        w.experiment_search.setText('nothing-matches')
        self.assertEqual(w.experiments.model().rowCount(),0)
        self.assertEqual(w.comparison_ids,[])

    def test_strategy_context_selects_relevant_scan_parameters(self):
        w=self.window
        w.quick_template.setCurrentIndex(w.quick_template.findData('rsi'))
        self.assertEqual(set(w.parameter_grid()),{'period','oversold'})
        self.assertIn('RSI',w.scan_context.text())
        self.assertEqual(w.template.currentData(),'rsi')
        w.quick_template.setCurrentIndex(w.quick_template.findData('buy_hold'))
        self.assertFalse(w.tune_button.isEnabled())
        self.assertTrue(w.quick_row.isHidden())

    def test_light_theme_updates_existing_text_and_survives_reopen(self):
        w=self.window
        w.show_result(self.result())
        w.toggle_theme()
        self.assertIs(w.colors,LIGHT)
        self.assertIn(LIGHT['text'],w.metric_labels['sharpe'].styleSheet())
        legend_label=w.charts.price.plotItem.legend.items[0][1]
        self.assertIn(LIGHT['text'],legend_label.item.toHtml())
        w.preferences.sync()
        other=Window(Service(self.home.name))
        self.assertIs(other.colors,LIGHT)
        other.close()
        for palette in (DARK,LIGHT):
            for foreground in ('text','muted','positive','negative'):
                for background in ('bg','panel','raised'):
                    self.assertGreaterEqual(contrast(palette[foreground],palette[background]),4.5,(foreground,background,palette))


if __name__=='__main__':unittest.main()
