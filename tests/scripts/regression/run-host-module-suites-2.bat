@echo off
REM Follow-up host run: suites that need a clean signal after the basetemp fix.
setlocal
cd /d C:\000_Capstone

set "LOGDIR=C:\000_Capstone\tests\results\host-module-suites"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\host-module-suites-run2.txt"
set "BASETEMP=%LOCALAPPDATA%\Temp\stats-pytest-host2"
if not exist "%BASETEMP%" mkdir "%BASETEMP%"
set "STATS_TESTDATA_DIR=C:\000_Capstone\tests\input"
set "STATS_PARSING_TESTDATA_DIR=C:\000_Capstone\tests\input"

echo Host module unit suites - run 2 (basetemp parent created)> "%LOG%"
echo Started: %DATE% %TIME%>> "%LOG%"

call :runsuite file_validation_module
call :runsuite data_validation_module
call :runsuite stats_data

echo.>> "%LOG%"
echo Finished: %DATE% %TIME%>> "%LOG%"
echo RESULT_MARKER_DONE>> "%LOG%"
exit /b 0

:runsuite
echo.>> "%LOG%"
echo === %1 ===>> "%LOG%"
if not exist "tests\unit\%1" (
    echo suite folder missing; skipped>> "%LOG%"
    goto :eof
)
pytest "tests\unit\%1" -q --basetemp "%BASETEMP%\%1" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo suite_exit=FAILED>> "%LOG%"
) else (
    echo suite_exit=PASSED>> "%LOG%"
)
goto :eof
