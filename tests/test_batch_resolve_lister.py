# tests/test_batch_resolve_lister.py
import inspect
from src.ui.components.batch_resolve_dialog import BatchResolveDialog


def test_init_accepts_lister_fn():
    sig = inspect.signature(BatchResolveDialog.__init__)
    assert "lister_fn" in sig.parameters, "BatchResolveDialog must accept lister_fn"
    assert sig.parameters["lister_fn"].default is None
