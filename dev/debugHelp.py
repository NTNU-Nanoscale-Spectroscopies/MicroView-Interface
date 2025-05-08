import inspect
import os

#Add id of message to be printed
match_id = []
# match_id.append("connecting")
# match_id.append("thread")
# match_id.append("spec")
match_id.append("")

def debugp(id, text):
    """
    Prints debug messages if the provided ID is in the match_id set.

    Parameters:
    id (str): Identifier to check against match_id.
    text (str): Debug message to print.

    Returns:
    None
    """

    if id.lower() not in match_id and "all" not in match_id:
        return

    frame = inspect.stack()[1]
    module = inspect.getmodule(frame[0])
    filename = os.path.basename(module.__file__)
    
    print("DEBUG -  " ,filename, " :: ", id, " - ", text)