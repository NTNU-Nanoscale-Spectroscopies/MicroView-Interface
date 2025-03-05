import inspect
import os

#connecting thread spec
match_id = []

def debugp(id, text):

    if id.lower() not in match_id:
        return

    frame = inspect.stack()[1]
    module = inspect.getmodule(frame[0])
    filename = os.path.basename(module.__file__)
    
    print("DEBUG -  " ,filename, " :: ", id, " - ", text)