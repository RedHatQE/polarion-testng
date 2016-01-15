"""
Parses a testng-results.xml file and

1. Creates a Test Case based on class.method_name
   - It will check to see if an existing Test Case with a matching title already exists and return it
   - Otherwise, it will create a new Test Case
2. It will create a Test Step to be included in the TestCase
   - Step will be stringified arguments
   - Expected Result will be passed
3. If there is an existing Test Case, check to see if it has steps
   - If it does not, create a new Test Case?
   - If does, but number of steps do not match?
4. If creating a new test case insert the Test Steps into it
5. For each Test Case update it
6. For each Test Case, create a matching Test Record

"""
from testng.logger import log
from testng.utils import *
from testng.decorators import retry, profile
from testng.parsing import parser

# Jenkins created environment variables
if 0:
    WORKSPACE = os.environ["WORKSPACE"]
    TEST_RUN_TEMPLATE = os.environ["TEST_RUN_TEMPLATE"]
    TESTNG_RESULTS_PATH = os.path.join(WORKSPACE, "test-output/testng-results.xml")


class Suite(object):
    """
    A collection of TestCase objects.
    """
    def __init__(self, results_root=None, project=None):
        if results_root is None:
            results_root = os.path.join(DEFAULT_WORKSPACE, DEFAULT_JENKINS_PROJECT, DEFAULT_RESULT_PATH)
        self.tests = parser(results_root)
        self._project = project

        not_skipped = filter(lambda x: x.status != SKIP, self.tests)
        for test_case in not_skipped:
            desc = test_case.description
            title = test_case.title

            t = lambda x: unicode.encode(x, encoding="utf-8", errors="ignore") if isinstance(x, unicode) else x
            desc, title = [t(x) for x in [desc, title]]

            log.info("Creating TestCase for {}: {}".format(title, desc))
            pyl_tc = test_case.create_polarion_tc()
            self._update_tc(pyl_tc)

    @property
    def project(self):
        if self._project is None:
            self._project = get_default_project()
        return self._project

    @project.setter
    def project(self, val):
        self._project = val

    @retry
    def _update_tr(self, test_run):
        test_run.update()

    @retry
    def _update_tc(self, test_case):
        test_case.update()

    @profile
    def create_test_run(self, template_id, test_run_base, runner="stoner"):
        """
        Creates a new Polarion TestRun

        :param template_id: id of the template to use for TestRun
        :param test_run_base: a str to look up most recent TestRuns (eg "Jenkins Run" if
                              the full name of TestRuns is "Jenkins Run 200"
        :param runner: str of the user id (eg stoner, not "Sean Toner")
        :return: None
        """
        tr = get_latest_test_run(test_run_base)
        new_id = make_test_run_id_from_latest(tr)
        log.info("Creating new Test Run ID: {}".format(new_id))
        test_run = TestRun.create(self.project, new_id, template_id)
        test_run.status = "inprogress"

        for tc in self.tests:
            tc.create_test_record(test_run, run_by=runner)

        test_run.status = "finished"
        self._update_tr(test_run)

    def update_test_run(self, test_run, runner="stoner"):
        """
        Given a TestRun object, update it given the TestCases contained in self

        :param test_run: pylarion TestRun object
        :param runner: the user who ran the tests
        :return: None
        """
        for tc in self.tests:
            # Check to see if the test case is already part of the test run
            if check_test_case_in_test_run(test_run, tc.polarion_tc.work_item_id):
                continue
            tc.create_test_record(test_run, run_by=runner)

    @staticmethod
    def get_test_run(test_run_id):
        """
        Looks for matching TestRun given a test_run_id string

        :param test_run_id:
        :return:
        """
        all_fields = filter(lambda x: not x.startswith("_"),
                            TestRun._cls_suds_map.keys())
        all_fields = list(all_fields) + [test_run_id]
        tr = TestRun.search('"{}"'.format(test_run_id), fields=all_fields,
                            sort="created")
        return tr

    def create_test_run_template(self, template_id, case_type="automatedProcess", query=None):
        """
        Creates a TestRun template that can be used as a basis for other TestRuns

        :param template_id: a unique str to give as ID for this template
        :param case_type:
        :param query:
        :return:
        """
        test_template = TestRun.create_template(self.project, template_id, query=query,
                                                select_test_cases_by=case_type)
        return test_template


if __name__ == "__main__":
    # Will auto-generate polarion TestCases
    suite = Suite("/home/stoner/Documents/testng/testng-results.xml")
    # If you already have a TestRun, you can update it
    # tr = Suite.get_test_run(tr_id)
    # suite.update_test_run(tr)
    # Once the suite object has been initialized, generate a test run with associated test records
    suite.create_test_run("sean toner test template", "pylarion exporter testing")
