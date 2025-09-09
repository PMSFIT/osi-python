Open Simulation Interface (OSI) Python Bindings
===============================================

This python package provides python bindings and utility modules for the [ASAM Open Simulation Interface](https://github.com/OpenSimulationInterface/open-simulation-interface).

For more information on OSI see the [official documentation](https://opensimulationinterface.github.io/osi-antora-generator/asamosi/latest/specification/index.html) or the [class list](https://opensimulationinterface.github.io/osi-antora-generator/asamosi/latest/gen/annotated.html) for defined protobuf messages.

Usage
-----

For usage examples, please refer to the official documentation:

- [Trace file generation with python](https://opensimulationinterface.github.io/osi-antora-generator/asamosi/latest/interface/architecture/trace_file_example.html)

Installation
------------

### Installing from source

#### Prerequisites

- You have installed Python 3.10 or later.
- You have installed _pip_.

#### Steps

- Open a terminal.
- Clone the osi-python repository, including sub-modules:

  ```console
  git clone --recurse-submodules https://github.com/OpenSimulationInterface/osi-python.git
  ```

- Switch to the repository directory:

  ```console
  cd osi-python
  ```

- Optionally create and activate a new virtual environment:

  ```console
  python3 -m venv venv
  source venv/bin/activate
  ```

- Install the package:

  ```console
  pip install .
  ```
