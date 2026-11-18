"""JUnit XML for unittest-based suites, standard library only (no extra dependency in the image).

Unit tests (Django):
    python manage.py test tests --testrunner tests.junit.DjangoJUnitRunner      # JUNIT_XML=path (default junit.xml)
E2E (plain unittest):
    python -m tests.junit e2e test-results/e2e.xml                              # discover <dir>, write <xml>
    python -m tests.junit e2e test-results/smoke.xml 'smoke*.py'                # optional file pattern

The file is the record of which tests ran and how they ended; CI uploads it as an artifact.
"""
import os
import sys
import time
import unittest
import xml.etree.ElementTree as ET


class JUnitResult(unittest.TextTestResult):
    """TextTestResult that also remembers every outcome with its duration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []  # (test_id, status, seconds, message)
        self._started = {}

    def startTest(self, test):
        self._started[test.id()] = time.monotonic()
        super().startTest(test)

    def _record(self, test, status, message=""):
        started = self._started.get(test.id(), time.monotonic())
        self.records.append((test.id(), status, time.monotonic() - started, message))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failure", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "passed")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "failure", "unexpected success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            status = "failure" if issubclass(err[0], test.failureException) else "error"
            self._record(subtest, status, self._exc_info_to_string(err, test))


def write_junit(records, path, suite_name):
    suite = ET.Element("testsuite", name=suite_name, tests=str(len(records)),
                       failures=str(sum(r[1] == "failure" for r in records)),
                       errors=str(sum(r[1] == "error" for r in records)),
                       skipped=str(sum(r[1] == "skipped" for r in records)),
                       time=f"{sum(r[2] for r in records):.3f}")
    for test_id, status, seconds, message in records:
        classname, _, name = test_id.rpartition(".")
        case = ET.SubElement(suite, "testcase", classname=classname, name=name, time=f"{seconds:.3f}")
        if status in ("failure", "error", "skipped"):
            ET.SubElement(case, status, message=message.strip().splitlines()[-1][:200] if message else "").text = message
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    root = ET.Element("testsuites")
    root.append(suite)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def summary_line(records):
    passed = sum(r[1] == "passed" for r in records)
    failed = sum(r[1] in ("failure", "error") for r in records)
    skipped = sum(r[1] == "skipped" for r in records)
    return f"{len(records)} tests: {passed} passed, {failed} failed, {skipped} skipped"


try:
    from django.test.runner import DiscoverRunner
except ImportError:  # E2E runs without Django installed
    DiscoverRunner = None

if DiscoverRunner is not None:
    class DjangoJUnitRunner(DiscoverRunner):
        """Django's default runner + JUnit XML written to $JUNIT_XML (default junit.xml)."""

        def get_resultclass(self):
            return JUnitResult

        def run_suite(self, suite, **kwargs):
            result = super().run_suite(suite, **kwargs)
            path = os.environ.get("JUNIT_XML", "junit.xml")
            write_junit(result.records, path, "unit")
            print(f"JUnit XML: {path} ({summary_line(result.records)})")
            return result


def main(argv):
    start_dir, path = argv[1], argv[2]
    pattern = argv[3] if len(argv) > 3 else "test*.py"
    name = os.path.basename(start_dir.rstrip("/")) if len(argv) <= 3 else pattern.split("*")[0].rstrip("_.")
    suite = unittest.defaultTestLoader.discover(start_dir, pattern=pattern, top_level_dir=start_dir)
    result = unittest.TextTestRunner(resultclass=JUnitResult, verbosity=2).run(suite)
    write_junit(result.records, path, name)
    print(f"JUnit XML: {path} ({summary_line(result.records)})")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
