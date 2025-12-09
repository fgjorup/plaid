# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

Generic Qt worker helper for running callables in a QThread.
"""
from PyQt6 import QtCore

class Worker(QtCore.QObject):
    """A simple QObject worker that runs a callable in a QThread.

    The Worker instance owns the QThread during execution and will clean up
    the thread when finished.
    """
    started = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal(bool, object)  # success(bool), result or exception
    error = QtCore.pyqtSignal(object)

    def __init__(self, func, args=None, kwargs=None, parent=None):
        super().__init__(parent)
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self._thread = None

    @QtCore.pyqtSlot()
    def _run(self):
        """Internal slot that executes the callable."""
        self.started.emit()
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(True, result)
        except Exception as e:
            # emit error signals and finished with failure
            self.error.emit(e)
            self.finished.emit(False, e)

    def start(self):
        """Start the worker in a new QThread."""
        if self._thread is not None and self._thread.isRunning():
            raise RuntimeError('Worker already running')
        self._thread = QtCore.QThread()
        # move self to thread and start
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        # ensure cleanup when finished
        self.finished.connect(lambda *_: self._cleanup())
        self._thread.start()

    def _cleanup(self):
        try:
            if self._thread is not None:
                self._thread.quit()
                self._thread.wait()
                self._thread = None
        except Exception:
            pass
    
    def cancel(self):
        """Cancel the worker if possible."""
        self._thread.terminate()
        self._cleanup()

def run_in_thread(func, args=None, kwargs=None, on_done=None):
    """Convenience helper: run func in background, call on_done(success, result) on finish.

    Returns the Worker instance (so caller can keep a reference or connect signals).
    """
    worker = Worker(func=func, args=args or (), kwargs=kwargs or {})
    if on_done:
        worker.finished.connect(on_done)
    worker.start()
    return worker
