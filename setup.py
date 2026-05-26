from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "terminalcrypt._cython.indicators_cy",
        ["terminalcrypt/_cython/indicators_cy.pyx"],
    )
]

setup(
    name="terminalcrypt",
    ext_modules=cythonize(extensions, compiler_directives={"language_level": 3}),
    zip_safe=False,
)
