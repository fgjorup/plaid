from setuptools import setup, find_packages
from plaid import __version__ as plaid_version

def readme():
    """Read the contents of the README file."""
    with open("README.md", "r", encoding="utf-8") as f:
        lines = f.readlines()
        # Remove lines containing '!['
        lines = [line for line in lines if not line.startswith("![")]  
        return "".join(lines)


setup(
    name="plaid-xrd",
    version=plaid_version,
    description="plaid is a simple visualization tool intended to quickly evaluate azimuthally integrated powder diffraction data",
    long_description=readme(),
    long_description_content_type="text/markdown",
    author="Frederik H Gjørup",
    author_email="fgjorup@chem.au.dk",
    url="https://github.com/fgjorup/plaid",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "h5py",
        "PyQt6>=6.8.1",
        "pyqtgraph>=0.13.7",
        "Dans-Diffraction>=3.0.0",
        "requests >= 2.25.0",
        "packaging >= 20.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
    python_requires=">=3.9",
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "plaid=plaid.plaid:main"
        ]
    },
)

