"""Repeatable native application acceptance, usable from the packaged executable."""
import json
import os
import time
import traceback
from pathlib import Path
from PySide6 import QtCore
from .service import Service, export_result
from .strategies import TEMPLATES


def schedule(app, window, directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    errors = []

    def fail(message, detail=''):
        errors.append(message)
        window.finish_job()
        (directory/'failed.json').write_text(json.dumps({'error':message,'detail':detail},ensure_ascii=False),encoding='utf-8')
        app.exit(1)
    window.error = fail

    def finish(result):
        try:
            window.show_result(result)
            app.processEvents()
            window.grab().save(str(directory/'desktop.png'))
            ds = result['dataset']['id']
            strategies = [dict(s) for s in TEMPLATES.values()]
            for strategy in strategies:
                window.service.store.save('strategy', strategy['name'], strategy)
            window.service.store.save('config','验收配置',{'dataset_id':ds,'strategy':result['strategy'],'config':result['config']})
            compared = window.service.compare(ds, strategies, {})
            tuned = window.service.tune(ds,TEMPLATES['sma'],{}, {'fast':[5,10,15],'slow':[20,30,60]})
            export_result(result,directory/'export')
            restored = Service(window.service.store.home).store.load(result['id'])['body']
            assert restored['summary'] == result['summary']
            assert len({r['summary']['start'] for r in tuned}) == 1
            assert len({r['summary']['start'] for r in compared}) == 1
            assert window.service.store.bars(ds,'2016-01-01','2016-01-31')
            for row in result['curve']:
                assert abs(row['cash']+row['market_value']-row['equity']) < 1e-6
                assert abs(row['realized_pnl']+row['unrealized_pnl']-row['pnl']) < 1e-6
            window.refresh()
            window.nav.setCurrentRow(4)
            for i,row in enumerate(window.experiments.model().rows):
                if row['id'] in {r['id'] for r in tuned}:
                    window.experiments.selectionModel().select(window.experiments.model().index(i,0),QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows)
            window.overlay()
            app.processEvents()
            window.grab().save(str(directory/'comparison.png'))
            report={'passed':True,'pid':os.getpid(),'rows':result['dataset']['metadata']['rows'],
                    'dataset':result['dataset'],'backtest':result['summary'],'compared_strategies':len(compared),
                    'parameter_runs':len(tuned),'seconds':time.perf_counter()-started,
                    'export_files':sorted(p.name for p in (directory/'export').iterdir()),
                    'storage':str(window.service.store.home),'packaged':bool(getattr(__import__('sys'),'frozen',False))}
            (directory/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            # Leave enough time for an external process to sample the native PID's sockets.
            QtCore.QTimer.singleShot(5000,app.quit)
        except Exception as exc:
            fail(str(exc),traceback.format_exc())

    def start():
        ds=window.service.store.datasets()[0]['id']
        window.select_dataset(ds)
        window.start_job('验收回测',lambda cancel,progress:window.service.backtest(ds,TEMPLATES['sma'],{},cancel=cancel),finish)
    QtCore.QTimer.singleShot(100,start)
