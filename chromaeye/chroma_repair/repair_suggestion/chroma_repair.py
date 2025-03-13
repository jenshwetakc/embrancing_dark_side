
'''
chroma eye generate suggestion report

## 1. Please make sure that you have passed the absolute path to the following:
        1. inconsistency report
        2. output file
'''
import os
import shutil
from chromaeye.chroma_repair.repair_suggestion.chroma_repair_suggestion import inconsistency_repair_suggestion

USRPROFILE = '~/Library/Application Support/Google/Chrome/'

def create_folder(folder_name):
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)
    return folder_name


# chroma repair
def chroma_repair(input_json_path, output_json_path):
    """
    Reads the JSON file, checks for inconsistencies, and generates a repair suggestion.
    """
    try:
        inconsistency_repair_suggestion(input_json_path, output_json_path)
    except Exception as e:
        print(f"Error processing the file: {e}")


def main():
    """
    Main function to execute the inconsistency check and repair suggestion generation.
    """

    base_path = "/chromaeye/example_dataset/partial_conversion/therichest"

    # Define paths for input and output
    input_file = os.path.join(base_path, "output/inconsistency.json")
    repair_folder = os.path.join(base_path, "repair")  # Ensure repair folder exists
    create_folder(repair_folder)  # Create repair folder if missing

    repair_suggestion = os.path.join(repair_folder, "repair_suggestion.json")

    chroma_repair(input_file, repair_suggestion)


if __name__ == "__main__":
    main()





