@echo off
setlocal
set APP_HOME=%~dp0
if "%APP_HOME%"=="" set APP_HOME=.
set CLASSPATH=%APP_HOME%gradle\wrapper\gradle-wrapper.jar
if defined JAVA_HOME (set JAVACMD=%JAVA_HOME%\bin\java.exe) else (set JAVACMD=java)
"%JAVACMD%" -classpath "%CLASSPATH%" -Dorg.gradle.appname=gradlew org.gradle.wrapper.GradleWrapperMain %*
