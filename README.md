<h1 align="center">
  <img src="dev/images/MicroView.ico" alt="MicroView Logo" width="100">
  <br>
  MicroView-Interface
  <br>
  <span style="font-size: 15px;"><i>by the NTNU Nanoscale Spectroscopies Team</i></span>
</h1>


## About the project
As part of the research conducted by the Nanoscale Spectroscopies Team, numerous microscopes are used, each accompanied by specific tools and software. This project, developed in Python, aims to centralize these devices and their functionalities within a single software platform. The goal is to simplify their management while enhancing the efficiency and productivity of research activities.


## Edit software
If you want to improve this software, follow the steps below to set up your environment and access the script. Make sure you have the latest versions of Python and pip installed.

### 1· Create a virtual environment
Run the following command to create a virtual environment in the project directory :
````bash
python -m venv .venv
````

### 2· Activate your virtual environment
Activate the virtual environment using the appropriate command for your operating system :
````bash
.venv\Scripts\activate       # On Windows
source .venv/bin/activate    # On macOs or Linux
````

### 3· Install the dependencies
Once the virtual environment is activated, install the project dependencies :
````bash
pip install -r requirements.txt
````

### 4· Build an executable
After making your modifications, you can build the project into an executable application by running :
````bash
pyinstaller microview.spec
````
The executable will be located in the `/dist` folder within your project directory.


## Contributors
This project would not have been possible without these contributors :

- **Angelos XOMALIS** - Project leader
- **Julia LÖVGREN** - Project supervisor
- **Noah JACOB** - Developer
