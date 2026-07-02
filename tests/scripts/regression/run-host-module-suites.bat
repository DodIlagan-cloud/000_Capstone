@echo off
REM M12 - Email Ingestion Module Start
REM Host-side module unit suites. Each module runs in a SEPARATE pytest process
REM because service modules share the top-level Python package name "app"
REM (mirrors tests\scripts\regression\run_module_unit_tests.ps1, which runs the
REM same suites inside the stats-runtime container).
REM --basetemp uses a fresh per-suite folder under %%LOCALAPPDATA%%\Temp to avoid
REM the repo-local pytest-tmp permission problem seen on this workstation.
REM Output: tests\results\host-module-suites\host-module-suites-latest.txt
REM M12 End
setlocal
cd /d C:\000_Capstone

set "LOGDIR=C:\000_Capstone\tests\results\host-module-suites"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\host-module-suites-latest.txt"
set "BASETEMP=%LOCALAPPDATA%\Temp\stats-pytest-host"
REM pytest requires the --basetemp parent to exist before it creates per-suite dirs.
if not exist "%BASETEMP%" mkdir "%BASETEMP%"
set "STATS_TESTDATA_DIR=C:\000_Capstone\tests\input"
set "STATS_PARSING_TESTDATA_DIR=C:\000_Capstone\tests\input"

echo Host module unit suites (separate pytest processes)> "%LOG%"
echo Started: %DATE% %TIME%>> "%LOG%"
echo basetemp root: %BASETEMP%>> "%LOG%"

call :runsuite email_ingestion_module
call :runsuite file_validation_module
call :runsuite identity_access_module
call :runsuite document_parsing_module
call :runsuite transaction_extraction_module
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
