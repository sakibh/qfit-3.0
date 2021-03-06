## Installing dependencies using pip

If you prefer the more traditional `pip` tool, dependencies can be installed
as follows

    pip install numpy scipy cvxopt

The CPLEX optimization suite is not available through `pip`. Obtain the CPLEX Community Edition by registering and downloading it from the [IBM website](https://www.ibm.com/products/ilog-cplex-optimization-studio). 

After installing and unpacking the software, install the CPLEX Python interface

    cd <CPLEX_ROOT>/cplex/python/<version>/x86_64_<PLATFORM>
    python setup.py install

where
- `<CPLEX_ROOT>` is the directory where you installed CPLEX, 
- `<version>` is the appropriate python version in your environment,
- `<PLATFORM>` is a platform dependent string, such as `linux` for Linux systems and `osx` for macOSX.
