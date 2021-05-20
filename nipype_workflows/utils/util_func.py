


def create_tuple_of_two_elem(elem1, elem2):
    tuple_elem = (elem1, elem2)
    return tuple_elem

def create_list_of_two_elem(elem1, elem2):
    list_elem = [elem1, elem2]
    return list_elem


def cat_2files(elem1, elem2):

    import os

    cat_file = os.path.abspath("cat_file.txt")

    with open(cat_file, 'w') as outfile:
        with open(elem1, 'r') as infile:
            outfile.write(infile.read())

        with open(elem1, 'r') as infile:
            outfile.write(infile.read())

    return cat_file



def paste_2files(elem1, elem2):

    import os

    paste_file = os.path.abspath("paste_file.txt")

    with open(paste_file, 'w') as outfile:

        with open(elem1, 'r') as infile1, open(elem2, 'r') as infile2:
            lines1 = infile1.readlines()
            lines2 = infile2.readlines()

            assert len(lines1)==len(lines2), \
                "Error, textfiles should have same number of lines"

            for line1, line2 in zip(lines1, lines2):
                print(line1.strip()+" "+line2)
                outfile.write(line1.strip()+" "+line2)

    return paste_file



