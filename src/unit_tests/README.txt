ServerManager Unit Test Framework
---------------------------------
1. First you need to set the unit-test environment for unit-testing.
   You can do that by running the setup_utenv.sh from the ../src/unit-tests directory
   This is a ONE TIME OPERATION
2. Add your unit-test code by creating a new directory for each functionality like it is done in monitoring
3. Add the test-suite that you are creating to the wrapper test-suite in  sm_unit_test.py
4. Run the test by running the script run_tests.sh script
5. Generate the code-coverage report by running the code_coverage.sh script
   You can go to the browser and see the report under http://<ipaddress>/figleafhtml directory
