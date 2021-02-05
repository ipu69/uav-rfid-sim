.PHONY: build_ext build dist redist install install-from-source clean uninstall

build_ext:
	CYTHONIZE=1 python setup.py build_ext --inplace

build:
	CYTHONIZE=1 python setup.py build

dist:
	CYTHONIZE=1 python setup.py sdist bdist_wheel

redist: clean dist

install:
	CYTHONIZE=1 pip install -e .

install-from-source: dist
	pip install dist/uav-rfid-sim-0.1.0.tar.gz

clean:
	$(RM) -r build dist src/*.egg-info src/*.so src/model/*.so
	$(RM) -r src/model/des/cyscheduler.{c,cpp}
	#$(RM) -r src/cypack/{utils.c,answer.c,fibonacci.c} src/cypack/sub/wrong.c
	$(RM) -r .pytest_cache
	find . -name __pycache__ -exec rm -r {} +
	#git clean -fdX

uninstall:
	pip uninstall uav-rfid-sim

