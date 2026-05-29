# Quickstart code - Except I'm using html
from unstructured.partition.html import partition_html
from unstructured.staging.base import elements_to_json

file_path = "<TODO: Enter file path to base_file_name>"
base_file_name = "<TODO: Enter file name>"

def main():
    elements = partition_html(filename=f"{file_path}/{base_file_name}.htm")
    elements_to_json(elements=elements, filename=f"{file_path}/{base_file_name}-output.json")

if __name__ == "__main__":
    main()
