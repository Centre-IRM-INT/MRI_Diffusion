"""
"""

import os

def read_json_info(json_file):

    import json
    print(json_file)


    data_dict = json.load(open(json_file))

    readout_time = data_dict['TotalReadoutTime']
    print("readout_time: {}".format(readout_time))

    return readout_time


def create_acq_files(bval_AP, bval_PA, readout_time):

    import os

    dict_rep = {'10':'0',
                '295':'300',
                '305':'300',
                '990':'1000',
                '995':'1000',
                '1005':'1000',
                '1010':'1000'}

    acq_param_file = os.path.abspath("acq_parameters")
    acq_index_file = os.path.abspath("acq_index")

    count = 0

    paramf = open(acq_param_file, "w")
    indexf = open(acq_index_file, "w")

    def replace(cur_list, cur_dict):
        return [cur_dict.get(item, item) for item in cur_list]

    with open(bval_AP, "r") as f:
        list_bval = f.readlines()[0].split()
        list_bval_new = replace(list_bval, dict_rep)

        for val_B  in list_bval_new:
            if val_B == '0':
                paramf.write("0 -1 0 {}\n".format(readout_time))
                count+=1
            indexf.write("{}\n".format(count))

    bval_AP_new_file = os.path.abspath("bval_AP_new")

    with open(bval_AP_new_file, "w") as f:
        f.write(" ".join(list_bval_new))

    with open(bval_PA, "r") as f:
        list_bval = f.readlines()[0].split()
        list_bval_new = replace(list_bval, dict_rep)

        for val_B  in list_bval_new:
            if val_B == '0':
                paramf.write("0 1 0 {}\n".format(readout_time))
                count+=1
            indexf.write("{}\n".format(count))


    bval_PA_new_file = os.path.abspath("bval_PA_new")

    with open(bval_PA_new_file, "w") as f:
        f.write(" ".join(list_bval_new))


    paramf.close()
    indexf.close()

    return acq_param_file, acq_index_file, bval_AP_new_file, bval_PA_new_file


def keep_even_slices(fmap_AP_PA_file):

    import os

    dimz = os.popen('fslval {}.nii.gz dim3'.format(fmap_AP_PA_file)).read()

    print("dimz = {}".format(dimz))

    if int(dimz)%2 == 1:

        print("Remove one slice from data to get even number of slices")
        tmp_file = os.path.abspath("up_down_b0")

        os.system("fslroi {}.nii.gz {}.nii.gz  0 -1 0 -1 1 -1".format(fmap_AP_PA_file, even_file))
        fmap_AP_PA_file = even_file

        dimz = os.popen('fslval {}.nii.gz dim3'.format(fmap_AP_PA_file)).read()

        print("After modif, dimz = {}".format(dimz))

    return fmap_AP_PA_file
