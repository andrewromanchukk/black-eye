"""On a failed E2E test, keep a screenshot of every open page and a Playwright trace of the whole test.

Saved under $E2E_ARTIFACTS (default test-results/e2e-failures)/<test id>/; CI uploads that folder as an artifact.
Open a trace with:  python -m playwright show-trace context1-trace.zip   (or https://trace.playwright.dev)
"""
import os
import re

ARTIFACTS = os.environ.get("E2E_ARTIFACTS", "test-results/e2e-failures")


def _failed(test) -> bool:
    result = test._outcome.result  # failures are recorded on the result as they happen (Python 3.11+)
    return any(getattr(t, "test_case", t) is test for t, _ in result.failures + result.errors)


def record_on_failure(test, context):
    """Start tracing `context`; when `test` ends, save trace + screenshots only if it failed. Call right after creating
    the context and after registering context.close() as a cleanup (cleanups run last-in, first-out)."""
    context.tracing.start(screenshots=True, snapshots=True)
    n = test.__dict__["_e2e_contexts"] = test.__dict__.get("_e2e_contexts", 0) + 1  # a test may open several

    def finish():
        if not _failed(test):
            context.tracing.stop()
            return
        folder = os.path.join(ARTIFACTS, re.sub(r"[^\w.-]+", "_", test.id()))
        os.makedirs(folder, exist_ok=True)
        for i, page in enumerate(context.pages):
            try:
                page.screenshot(path=os.path.join(folder, f"context{n}-page{i}.png"), full_page=True)
            except Exception:  # a crashed page must not hide the real failure
                pass
        context.tracing.stop(path=os.path.join(folder, f"context{n}-trace.zip"))
        print(f"\nE2E failure artifacts: {folder}")

    test.addCleanup(finish)
