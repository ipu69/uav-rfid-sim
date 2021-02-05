#!/usr/bin/python3
# Original version taken from:
# - https://github.com/FedericoStra/cython-package-example/blob/master/setup.py
import os

import numpy
from setuptools import setup, find_packages, Extension

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None


# https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#distributing-cython-modules
def no_cythonize(extensions, **_ignore):
    for extension in extensions:
        sources = []
        for sfile in extension.sources:
            path, ext = os.path.splitext(sfile)
            if ext in (".pyx", ".py"):
                if extension.language == "c++":
                    ext = ".cpp"
                else:
                    ext = ".c"
                sfile = path + ext
            sources.append(sfile)
        extension.sources[:] = sources
    return extensions


extensions = [
    Extension("model.des.cyscheduler", ["src/model/des/cyscheduler.pyx"],
              include_dirs=['src/model/des/'],
              language="c++",
              extra_compile_args=["-std=c++11"],
              extra_link_args=["-std=c++11"],
              ),
    # Extension("model.c1g2", ["src/model/c1g2/messages.pyx"]),
    # Extension(
    #    "cypack.sub.wrong",
    #    ["src/cypack/sub/wrong.pyx", "src/cypack/sub/helper.c"]
    # ),
]

CYTHONIZE = bool(int(os.getenv("CYTHONIZE", 0))) and cythonize is not None

if CYTHONIZE:
    compiler_directives = {
        "language_level": 3,
        "embedsignature": True,
    }
    extensions = cythonize(extensions, compiler_directives=compiler_directives,
                           annotate=True)
else:
    extensions = no_cythonize(extensions)

with open("requirements.txt") as fp:
    install_requires = fp.read().strip().split("\n")

with open("requirements-dev.txt") as fp:
    dev_requires = fp.read().strip().split("\n")

setup(
    ext_modules=extensions,
    packages=['model'],
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
        "docs": ["sphinx", "sphinx-rtd-theme"]
    },
)
