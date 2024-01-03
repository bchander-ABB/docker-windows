FROM mcr.microsoft.com/windows/servercore:ltsc2022
#FROM mcr.microsoft.com/dotnet/framework/sdk:4.8-windowsservercore-ltsc2019
SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

ENV PYTHONIOENCODING UTF-8

ENV PYTHON_VERSION 3.11.6

ENV http_proxy=http://geo-cluster125184-swg.ibosscloud.com:8082
ENV https_proxy=http://geo-cluster125184-swg.ibosscloud.com:8082
ENV HTTP_PROXY=http://geo-cluster125184-swg.ibosscloud.com:8082
ENV HTTPS_PROXY=http://geo-cluster125184-swg.ibosscloud.com:8082

RUN $url = ('https://www.python.org/ftp/python/{0}/python-{1}-amd64.exe' -f ($env:PYTHON_VERSION -replace '[a-z]+[0-9]*$', ''), $env:PYTHON_VERSION); \
	Write-Host ('Downloading {0} ...' -f $url); \
	[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; \
	Invoke-WebRequest -Uri $url -OutFile 'python.exe'; \
	\
	Write-Host 'Installing ...'; \
# https://docs.python.org/3/using/windows.html#installing-without-ui
	$exitCode = (Start-Process python.exe -Wait -NoNewWindow -PassThru \
		-ArgumentList @( \
			'/quiet', \
			'InstallAllUsers=1', \
			'TargetDir=C:\Python', \
			'PrependPath=1', \
			'Shortcuts=0', \
			'Include_doc=0', \
			'Include_pip=0', \
			'Include_test=0' \
		) \
	).ExitCode; \
	if ($exitCode -ne 0) { \
		Write-Host ('Running python installer failed with exit code: {0}' -f $exitCode); \
		Get-ChildItem $env:TEMP | Sort-Object -Descending -Property LastWriteTime | Select-Object -First 1 | Get-Content; \
		exit $exitCode; \
	} \
	\
# the installer updated PATH, so we should refresh our local value
	$env:PATH = [Environment]::GetEnvironmentVariable('PATH', [EnvironmentVariableTarget]::Machine); \
	\
	Write-Host 'Verifying install ...'; \
	Write-Host '  python --version'; python --version; \
	\
	Write-Host 'Removing ...'; \
	Remove-Item python.exe -Force; \
	Remove-Item $env:TEMP/Python*.log -Force; \
	\
	Write-Host 'Complete.'

# if this is called "PIP_VERSION", pip explodes with "ValueError: invalid truth value '<VERSION>'"
ENV PYTHON_PIP_VERSION 23.2.1
# https://github.com/docker-library/python/issues/365
ENV PYTHON_SETUPTOOLS_VERSION 65.5.1
# https://github.com/pypa/get-pip
ENV PYTHON_GET_PIP_URL https://github.com/pypa/get-pip/raw/4cfa4081d27285bda1220a62a5ebf5b4bd749cdb/public/get-pip.py
ENV PYTHON_GET_PIP_SHA256 9cc01665956d22b3bf057ae8287b035827bfd895da235bcea200ab3b811790b6

RUN Write-Host ('Downloading get-pip.py ({0}) ...' -f $env:PYTHON_GET_PIP_URL); \
	[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; \
	Invoke-WebRequest -Uri $env:PYTHON_GET_PIP_URL -OutFile 'get-pip.py'; \
	Write-Host ('Verifying sha256 ({0}) ...' -f $env:PYTHON_GET_PIP_SHA256); \
	if ((Get-FileHash 'get-pip.py' -Algorithm sha256).Hash -ne $env:PYTHON_GET_PIP_SHA256) { \
		Write-Host 'FAILED!'; \
		exit 1; \
	}; \
	\
	$env:PYTHONDONTWRITEBYTECODE = '1'; \
	\
	Write-Host ('Installing pip=={0} ...' -f $env:PYTHON_PIP_VERSION); \
	python get-pip.py \
		--disable-pip-version-check \
		--no-cache-dir \
		--no-compile \
		('pip=={0}' -f $env:PYTHON_PIP_VERSION) \
		('setuptools=={0}' -f $env:PYTHON_SETUPTOOLS_VERSION) \
	; \
	Remove-Item get-pip.py -Force; \
	\
	Write-Host 'Verifying pip install ...'; \
	pip --version; \
	\
	Write-Host 'Complete.'


# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app
#ARG HTTP_PROXY
#ARG HTTPS_PROXY
#COPY nuget.exe .
ENV http_proxy http://gateway.zscaler.net:443
ENV https_proxy http://gateway.zscaler.net:443


#RUN powershell -Command Invoke-WebRequest -Uri https://dist.nuget.org/win-x86-commandline/latest/nuget.exe -OutFile nuget.exe

# Set the NO_PROXY environment variable
#ENV NO_PROXY=localhost,127.0.0.1
#RUN pip install --index-url=https://pypi.python.org/simple/ --upgrade --no-cache-dir requests
#FROM python:3.10-slim

#ADD https://aka.ms/nugetclidl nuget.exe
#ENV PYVER=3.11.5
#RUN nuget.exe install python -ExcludeVersion -Version %PYVER% -OutputDirectory .

#ENV PATH=%PATH%;c:\inside\python\tools;c:\inside\python\tools\Scripts

# Install any needed packages specified in requirements.txt
RUN python -m pip install --trusted-host pypi.org --proxy http://gateway.zscaler.net:443 --no-cache-dir -r requirements.txt --user 
RUN python -m pip install --trusted-host pypi.org --no-cache-dir -r requirements.txt --user

# Make port 8501 available to the world outside this co	ntainer
EXPOSE 8000

# Run streamlit when the container launches
CMD ["streamlit", "run", "RFQ_Commercial_docker_docAI.py", "--server.port", "8000", "--server.address", "0.0.0.0"]

