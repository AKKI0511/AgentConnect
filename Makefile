install:
	pip install --upgrade pip &&\
		pip install -r requirements.txt

lint:
	flake8 --extend-ignore E501,W293,E128 src/