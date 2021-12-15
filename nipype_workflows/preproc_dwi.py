import os.path as op

import nipype.pipeline.engine as pe

from nipype.interfaces import spm as spm
from nipype.interfaces import fsl as fsl
import nipype.interfaces.fsl.dti as dti
from nipype.interfaces import utility as niu
import nipype.interfaces.io as nio

import nipype.interfaces.mrtrix3.preprocess as mrt
import nipype.interfaces.mrtrix3.utils as umrt

from nipype.interfaces.spm import preprocess as preproc

import nipype.algorithms.modelgen as model

from nipype.interfaces.spm import utils as spmu

from nodes.prepare import FslOrient

from nodes.function import read_json_info, create_acq_files, create_mean_acq_files, return_b0_even
from utils.util_func import paste_2files, create_tuple_of_two_elem, create_list_of_two_elem


from define_variables import *

#import nipype.interfaces.matlab as mlab
#~ mlab.MatlabCommand.set_default_matlab_cmd("matlab -nodesktop -nosplash") #comment on lance matlab sans la console matlab

def get_first(string_list):
    if isinstance(string_list, list):
        return string_list[0]
    else:
        return string_list


def _create_reorientstd_pipeline(name="reorient_pipe",
                              new_dims=("-x", "y", "z")):
    """
    By kepkee:
    fslswapdim image_bad x z -y image_good
    fslorient -deleteorient image_good.nii.gz;
    fslorient -setqformcode 1 image_good.nii.gz
    """

    # creating pipeline
    reorient_pipe = pe.Workflow(name=name)

    # Creating input node
    inputnode = pe.Node(
        niu.IdentityInterface(fields=['image']),
        name='inputnode'
    )

    reorient2std = pe.Node(fsl.Reorient2Std(), name="reorient2std")
    reorient_pipe.connect(inputnode, 'image', reorient2std, 'in_file')

    swap_dim = pe.Node(fsl.SwapDimensions(new_dims=new_dims), name="swap_dim")
    reorient_pipe.connect(reorient2std, 'out_file', swap_dim, 'in_file')

    reorient = pe.Node(FslOrient(main_option="swaporient"), name="reorient")
    reorient_pipe.connect(swap_dim, 'out_file', reorient, 'in_file')

    return reorient_pipe


def create_reorient_pipe(reorient_dims, wf_name="reorient_pipe"):

    reorient_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_AP', 'dwi_PA','T1w']),
        name='inputnode')

    # reorient2std
    reorient_dwi_AP = _create_reorientstd_pipeline(name="reorient_dwi_AP", new_dims=reorient_dims)
    reorient_pipe.connect(inputnode, 'dwi_AP', reorient_dwi_AP, 'inputnode.image')

    reorient_dwi_PA = _create_reorientstd_pipeline(name="reorient_dwi_PA", new_dims=reorient_dims)
    reorient_pipe.connect(inputnode, 'dwi_PA', reorient_dwi_PA, 'inputnode.image')

    reorient_T1w = _create_reorientstd_pipeline(name="reorient_T1w", new_dims=reorient_dims)
    reorient_pipe.connect(inputnode, 'T1w', reorient_T1w, 'inputnode.image')


    outputnode = pe.Node(niu.IdentityInterface(
        fields=['reoriented_dwi_AP', 'reoriented_dwi_PA','reoriented_T1w']),
        name='outputnode')

    reorient_pipe.connect(reorient_T1w, 'reorient.out_file',  outputnode, 'reoriented_T1w')
    reorient_pipe.connect(reorient_dwi_AP, 'reorient.out_file',  outputnode, 'reoriented_dwi_AP')
    reorient_pipe.connect(reorient_dwi_PA, 'reorient.out_file',  outputnode, 'reoriented_dwi_PA')

    return reorient_pipe

def create_preprocess_dwi_pipe(wf_name='preprocess_dwi_pipe'):

    """
    Preprocessing old fashioned normalize struct -> mean funct with SPM12
    """
    preprocess_dwi_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_AP','bval_AP','bvec_AP',
                'dwi_PA','bval_PA','bvec_PA']),
        name='inputnode')

    # denoise
    denoise_AP = pe.Node(interface=mrt.DWIDenoise(), name="denoise_AP")
    preprocess_dwi_pipe.connect(inputnode, 'dwi_AP',
                            denoise_AP, 'in_file')

    denoise_PA = pe.Node(interface=mrt.DWIDenoise(), name="denoise_PA")
    preprocess_dwi_pipe.connect(inputnode, 'dwi_PA',
                            denoise_PA, 'in_file')

    # degibbs
    degibbs_AP = pe.Node(interface=mrt.MRDeGibbs(), name="degibbs_AP")
    degibbs_AP.inputs.axes = [0,1]
    preprocess_dwi_pipe.connect(denoise_AP, 'out_file',
                            degibbs_AP, 'in_file')

    degibbs_PA = pe.Node(interface=mrt.MRDeGibbs(), name="degibbs_PA")
    degibbs_PA.inputs.axes = [0,1]
    preprocess_dwi_pipe.connect(denoise_PA, 'out_file',
                            degibbs_PA, 'in_file')

    # extract_b0
    extract_b0 = pe.Node(interface=fsl.ExtractROI(), name="extract_b0")
    extract_b0.inputs.args = "0 1"
    preprocess_dwi_pipe.connect(degibbs_AP, 'out_file', extract_b0, 'in_file')

    # bet_b0
    bet_b0 = pe.Node(interface=fsl.BET(), name="bet_b0")
    bet_b0.inputs.mask = True
    bet_b0.inputs.args = "-f 0.3"
    preprocess_dwi_pipe.connect(extract_b0, 'roi_file', bet_b0, 'in_file')

    # dtifit
    dtifit = pe.Node(interface=dti.DTIFit(), name="dtifit")
    preprocess_dwi_pipe.connect(degibbs_AP, 'out_file', dtifit, 'dwi')
    preprocess_dwi_pipe.connect(bet_b0, 'mask_file', dtifit, 'mask')
    preprocess_dwi_pipe.connect(inputnode, 'bvec_AP', dtifit, 'bvecs')
    preprocess_dwi_pipe.connect(inputnode, 'bval_AP', dtifit, 'bvals')


    outputnode = pe.Node(niu.IdentityInterface(
        fields=['preproc_dwi_AP', 'preproc_dwi_PA']),
        name='outputnode')

    preprocess_dwi_pipe.connect(degibbs_AP, 'out_file', outputnode, 'preproc_dwi_AP')
    preprocess_dwi_pipe.connect(degibbs_PA, 'out_file', outputnode, 'preproc_dwi_PA')

    return preprocess_dwi_pipe

def create_mean_acq_pipe(wf_name='acq_pipe'):

    """
    Preprocessing old fashioned normalize struct -> mean funct with SPM12
    """
    acq_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['bval_AP','json_AP', 'bval_PA','json_PA']),

        #fields=['dwi_AP', 'json_AP',
        #        'dwi_PA','bval_PA','bvec_PA', 'json_PA']),

        name='inputnode')

    # read json
    read_json = pe.Node(interface=niu.Function(input_names = ["json_file"], output_names = ["readout_time"], function = read_json_info), name="read_json")

    acq_pipe.connect(inputnode, 'json_AP', read_json, 'json_file')

    # create acq files
    acq = pe.Node(interface=niu.Function(input_names = ["bval_AP", "bval_PA", "readout_time"], output_names = ["acq_param_file", "acq_index_file", "bval_AP_new_file", "bval_PA_new_file"], function = create_mean_acq_files), name="acq")

    acq_pipe.connect(inputnode, 'bval_AP', acq, 'bval_AP')
    acq_pipe.connect(inputnode, 'bval_PA', acq, 'bval_PA')
    acq_pipe.connect(read_json, 'readout_time', acq, 'readout_time')

    return acq_pipe

def create_acq_pipe(wf_name='acq_pipe'):

    """
    Preprocessing old fashioned normalize struct -> mean funct with SPM12
    """
    acq_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['bval_AP','json_AP', 'bval_PA','json_PA']),

        #fields=['dwi_AP', 'json_AP',
        #        'dwi_PA','bval_PA','bvec_PA', 'json_PA']),

        name='inputnode')

    # read json
    read_json = pe.Node(interface=niu.Function(input_names = ["json_file"], output_names = ["readout_time"], function = read_json_info), name="read_json")

    acq_pipe.connect(inputnode, 'json_AP', read_json, 'json_file')

    # create acq files
    acq = pe.Node(interface=niu.Function(input_names = ["bval_AP", "bval_PA", "readout_time"], output_names = ["acq_param_file", "acq_index_file", "bval_AP_new_file", "bval_PA_new_file"], function = create_acq_files), name="acq")

    acq_pipe.connect(inputnode, 'bval_AP', acq, 'bval_AP')
    acq_pipe.connect(inputnode, 'bval_PA', acq, 'bval_PA')
    acq_pipe.connect(read_json, 'readout_time', acq, 'readout_time')

    return acq_pipe

def create_mean_topup_pipe(wf_name="topup_pipe"):

    topup_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_AP','bval_AP_new_file','bvec_AP', 'dwi_PA','bval_PA_new_file','bvec_PA','acq_param_file']),

        #fields=['dwi_AP', 'json_AP',
        #        'dwi_PA','bval_PA','bvec_PA', 'json_PA']),

        name='inputnode')

    # dwi_extract
    # AP
    tuple_AP = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["tuple_elem"], function = create_tuple_of_two_elem), name="tuple_AP")

    topup_pipe.connect(inputnode, 'bvec_AP', tuple_AP, 'elem1')
    topup_pipe.connect(inputnode, 'bval_AP_new_file', tuple_AP, 'elem2')

    dwi_extract_AP = pe.Node(interface=umrt.DWIExtract(), name="dwi_extract_AP")
    dwi_extract_AP.inputs.bzero = True
    dwi_extract_AP.inputs.out_file = "b0_AP.nii.gz"

    topup_pipe.connect(tuple_AP, 'tuple_elem', dwi_extract_AP, 'grad_fsl')
    topup_pipe.connect(inputnode, 'dwi_AP', dwi_extract_AP, 'in_file')

    # PA
    tuple_PA = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["tuple_elem"], function = create_tuple_of_two_elem), name="tuple_PA")

    topup_pipe.connect(inputnode, 'bvec_PA', tuple_PA, 'elem1')
    topup_pipe.connect(inputnode, 'bval_PA_new_file', tuple_PA, 'elem2')

    dwi_extract_PA = pe.Node(interface=umrt.DWIExtract(), name="dwi_extract_PA")
    dwi_extract_PA.inputs.bzero = True
    dwi_extract_PA.inputs.out_file = "b0_PA.nii.gz"

    topup_pipe.connect(tuple_PA, 'tuple_elem', dwi_extract_PA, 'grad_fsl')
    topup_pipe.connect(inputnode, 'dwi_PA', dwi_extract_PA, 'in_file')

    # average_b0_AP
    average_b0_AP =  pe.Node(interface=fsl.MeanImage(), name="average_b0_AP")
    average_b0_AP.inputs.dimension = "T"


    topup_pipe.connect(dwi_extract_AP, 'out_file', average_b0_AP, 'in_file')

    # average_b0_PA
    average_b0_PA =  pe.Node(interface=fsl.MeanImage(), name="average_b0_PA")
    average_b0_PA.inputs.dimension = "T"


    topup_pipe.connect(dwi_extract_PA, 'out_file', average_b0_PA, 'in_file')

    # merge_b0_AP_PA
    merge_2files = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["list_elem"], function = create_list_of_two_elem), name="merge_2files")

    topup_pipe.connect(average_b0_AP, 'out_file', merge_2files, 'elem1')
    topup_pipe.connect(average_b0_PA, 'out_file', merge_2files, 'elem2')

    merge_b0_AP_PA =  pe.Node(interface=fsl.Merge(), name="merge_b0_AP_PA")
    merge_b0_AP_PA.inputs.dimension = "t"

    topup_pipe.connect(merge_2files, 'list_elem', merge_b0_AP_PA, 'in_files')

    # keep even slices
    return_b02b0_for_b0 = pe.Node(interface=niu.Function(input_names = ["fmap_AP_PA_file"], output_names = ["b02b0_file"], function = return_b0_even), name="even_slices")

    topup_pipe.connect(merge_b0_AP_PA, 'merged_file', return_b02b0_for_b0, 'fmap_AP_PA_file')


    # topup
    topup = pe.Node(interface=fsl.TOPUP(), name="topup")
    topup_pipe.connect(return_b02b0_for_b0, 'b02b0_file', topup, "config")

    topup_pipe.connect(merge_b0_AP_PA, 'merged_file', topup, "in_file")
    topup_pipe.connect(inputnode, 'acq_param_file', topup, "encoding_file")

    ###########################################################################
    ## Eddy could be split here between topup and eddy?
    ###########################################################################
    # mean
    mean_unwarped_b0 = pe.Node(interface=fsl.MeanImage(), name="mean_unwarped_b0")
    topup_pipe.connect(topup, "out_corrected", mean_unwarped_b0, 'in_file')

    # bet unwarped b0
    bet_unwarped_b0 = pe.Node(interface=fsl.BET(), name="bet_unwarped_b0")
    bet_unwarped_b0.inputs.mask = True
    bet_unwarped_b0.inputs.args = "-f 0.3"
    topup_pipe.connect(mean_unwarped_b0, 'out_file',
                            bet_unwarped_b0, 'in_file')

    # mask_unwarped_b0
    mask_unwarped_b0 = pe.Node(interface=fsl.Threshold(), name="mask_unwarped_b0")
    mask_unwarped_b0.inputs.thresh = 0
    mask_unwarped_b0.inputs.args = " -bin "

    topup_pipe.connect(bet_unwarped_b0, 'out_file', mask_unwarped_b0, 'in_file')

    return topup_pipe


def create_topup_pipe(wf_name="topup_pipe"):

    topup_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_AP','bval_AP_new_file','bvec_AP', 'dwi_PA','bval_PA_new_file','bvec_PA','acq_param_file']),
        name='inputnode')

    # dwi_extract
    # AP
    tuple_AP = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["tuple_elem"], function = create_tuple_of_two_elem), name="tuple_AP")

    topup_pipe.connect(inputnode, 'bvec_AP', tuple_AP, 'elem1')
    topup_pipe.connect(inputnode, 'bval_AP_new_file', tuple_AP, 'elem2')

    dwi_extract_AP = pe.Node(interface=umrt.DWIExtract(), name="dwi_extract_AP")
    dwi_extract_AP.inputs.bzero = True
    dwi_extract_AP.inputs.out_file = "b0_AP.nii.gz"

    topup_pipe.connect(tuple_AP, 'tuple_elem', dwi_extract_AP, 'grad_fsl')
    topup_pipe.connect(inputnode, 'dwi_AP', dwi_extract_AP, 'in_file')

    # PA
    tuple_PA = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["tuple_elem"], function = create_tuple_of_two_elem), name="tuple_PA")

    topup_pipe.connect(inputnode, 'bvec_PA', tuple_PA, 'elem1')
    topup_pipe.connect(inputnode, 'bval_PA_new_file', tuple_PA, 'elem2')

    dwi_extract_PA = pe.Node(interface=umrt.DWIExtract(), name="dwi_extract_PA")
    dwi_extract_PA.inputs.bzero = True
    dwi_extract_PA.inputs.out_file = "b0_PA.nii.gz"

    topup_pipe.connect(tuple_PA, 'tuple_elem', dwi_extract_PA, 'grad_fsl')
    topup_pipe.connect(inputnode, 'dwi_PA', dwi_extract_PA, 'in_file')

    # merge_b0_AP_PA
    merge_2files = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["list_elem"], function = create_list_of_two_elem), name="merge_2files")

    topup_pipe.connect(dwi_extract_AP, 'out_file', merge_2files, 'elem1')
    topup_pipe.connect(dwi_extract_PA, 'out_file', merge_2files, 'elem2')

    merge_b0_AP_PA =  pe.Node(interface=fsl.Merge(), name="merge_b0_AP_PA")
    merge_b0_AP_PA.inputs.dimension = "t"

    topup_pipe.connect(merge_2files, 'list_elem', merge_b0_AP_PA, 'in_files')

    # keep even slices
    return_b02b0_for_b0 = pe.Node(interface=niu.Function(input_names = ["fmap_AP_PA_file"], output_names = ["b02b0_file"], function = return_b0_even), name="even_slices")

    topup_pipe.connect(merge_b0_AP_PA, 'merged_file', return_b02b0_for_b0, 'fmap_AP_PA_file')


    # topup
    topup = pe.Node(interface=fsl.TOPUP(), name="topup")
    topup_pipe.connect(return_b02b0_for_b0, 'b02b0_file', topup, "config")

    topup_pipe.connect(merge_b0_AP_PA, 'merged_file', topup, "in_file")
    topup_pipe.connect(inputnode, 'acq_param_file', topup, "encoding_file")

    ###########################################################################
    ## Eddy could be split here between topup and eddy?
    ###########################################################################
    # mean
    mean_unwarped_b0 = pe.Node(interface=fsl.MeanImage(), name="mean_unwarped_b0")
    topup_pipe.connect(topup, "out_corrected", mean_unwarped_b0, 'in_file')

    # bet unwarped b0
    bet_unwarped_b0 = pe.Node(interface=fsl.BET(), name="bet_unwarped_b0")
    bet_unwarped_b0.inputs.mask = True
    bet_unwarped_b0.inputs.args = "-f 0.3"
    topup_pipe.connect(mean_unwarped_b0, 'out_file',
                            bet_unwarped_b0, 'in_file')

    # mask_unwarped_b0
    mask_unwarped_b0 = pe.Node(interface=fsl.Threshold(), name="mask_unwarped_b0")
    mask_unwarped_b0.inputs.thresh = 0
    mask_unwarped_b0.inputs.args = " -bin "

    topup_pipe.connect(bet_unwarped_b0, 'out_file', mask_unwarped_b0, 'in_file')

    return topup_pipe

def create_eddy_pipe(wf_name="eddy_pipe", eddy_method = "lsr"):

    eddy_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_AP','bval_AP_new_file','bvec_AP',
                'dwi_PA','bval_PA_new_file','bvec_PA',
                'acq_param_file', 'acq_index_file', 'b0_mask',
                'topup_fieldcoef', 'topup_movpar']),

        name='inputnode')

    ######################################## full eddy ########################
    # paste bvec
    paste_bvec = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["paste_file"], function = paste_2files), name="paste_bvec")

    eddy_pipe.connect(inputnode, 'bvec_AP', paste_bvec, 'elem1')
    eddy_pipe.connect(inputnode, 'bvec_PA', paste_bvec, 'elem2')

    # paste bval
    paste_bval = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["paste_file"], function = paste_2files), name="paste_bval")

    eddy_pipe.connect(inputnode, 'bval_AP_new_file', paste_bval, 'elem1')
    eddy_pipe.connect(inputnode, 'bval_PA_new_file', paste_bval, 'elem2')

    # merge_data_AP_PA
    merge_data_2files = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["list_elem"], function = create_list_of_two_elem), name="merge_data_2files")

    eddy_pipe.connect(inputnode, 'dwi_AP', merge_data_2files, 'elem1')
    eddy_pipe.connect(inputnode, 'dwi_PA', merge_data_2files, 'elem2')

    merge_data_AP_PA =  pe.Node(interface=fsl.Merge(), name="merge_data_AP_PA")
    merge_data_AP_PA.inputs.dimension = "t"

    eddy_pipe.connect(merge_data_2files, 'list_elem', merge_data_AP_PA, 'in_files')

    # eddy
    eddy = pe.Node(interface=fsl.Eddy(), name="eddy")
    eddy.inputs.is_shelled = True

    eddy.inputs.dont_peas=True
    
    eddy.inputs.method=eddy_method
    
    eddy.inputs.fep=True

    eddy_pipe.connect(merge_data_AP_PA, 'merged_file', eddy, 'in_file')
    eddy_pipe.connect(inputnode, 'b0_mask', eddy, 'in_mask')

    eddy_pipe.connect(inputnode, 'acq_index_file', eddy, 'in_index')
    eddy_pipe.connect(inputnode, 'acq_param_file', eddy, 'in_acqp')

    eddy_pipe.connect(inputnode, 'topup_fieldcoef', eddy, 'in_topup_fieldcoef')
    eddy_pipe.connect(inputnode, 'topup_movpar', eddy, 'in_topup_movpar')

    eddy_pipe.connect(paste_bval, 'paste_file', eddy, 'in_bval')
    eddy_pipe.connect(paste_bvec, 'paste_file', eddy, 'in_bvec')

    return eddy_pipe

def create_post_eddy_pipe(wf_name="post_eddy_pipe", eddy_method="lsr"):

    post_eddy_pipe = pe.Workflow(name=wf_name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_corrected','bvals','rotated_bvecs']),

        name='inputnode')

    ###########################################################################
    # post eddy
    ###########################################################################

    # abs_eddy
    abs_eddy = pe.Node(interface=fsl.UnaryMaths(), name="abs_eddy")
    abs_eddy.inputs.operation = "abs"

    post_eddy_pipe.connect(inputnode, 'dwi_corrected', abs_eddy, "in_file")

    # rotated_bvecs
    tuple_rotated_bvec = pe.Node(
        interface=niu.Function(input_names = ["elem1", "elem2"],
                               output_names = ["tuple_elem"],
                               function = create_tuple_of_two_elem),
        name="tuple_rotated_bvec")

    post_eddy_pipe.connect(inputnode, 'rotated_bvecs', tuple_rotated_bvec, 'elem1')
    post_eddy_pipe.connect(inputnode, 'bvals', tuple_rotated_bvec, 'elem2')


    
    # the input of dwi_mask is dependent on the eddy_method
    # - if 'lsr', the abs_eddyneeds to be duplicated 
    # - if 'jac', the input is directly the abs_eddy
    if eddy_method=="lsr":
            
        # list_abs_eddy
        list_abs_eddy = pe.Node(interface=niu.Function(input_names = ["elem1", "elem2"], output_names = ["list_elem"], function = create_list_of_two_elem), name="list_abs_eddy")

        post_eddy_pipe.connect(abs_eddy, 'out_file', list_abs_eddy, 'elem1')
        post_eddy_pipe.connect(abs_eddy, 'out_file', list_abs_eddy, 'elem2')

        # merge_abs_eddy
        merge_abs_eddy =  pe.Node(interface=fsl.Merge(), name="merge_abs_eddy")
        merge_abs_eddy.inputs.dimension = "t"

        post_eddy_pipe.connect(list_abs_eddy, 'list_elem', merge_abs_eddy, 'in_files')

        # dwi_mask
        dwi_mask = pe.Node(interface=umrt.BrainMask(), name="dwi_mask")
        dwi_mask.inputs.out_file = "brainmask.nii.gz"

        post_eddy_pipe.connect(tuple_rotated_bvec, 'tuple_elem', dwi_mask, 'grad_fsl')
        post_eddy_pipe.connect(merge_abs_eddy, 'merged_file', dwi_mask, 'in_file')

        # dwi_bias_correct
        dwi_bias_correct = pe.Node(interface=mrt.DWIBiasCorrect(),
                                   name="dwi_bias_correct")
        dwi_bias_correct.inputs.use_ants = True

        post_eddy_pipe.connect(tuple_rotated_bvec, 'tuple_elem', dwi_bias_correct, 'grad_fsl')
        post_eddy_pipe.connect(merge_abs_eddy, 'merged_file', dwi_bias_correct, 'in_file')
        post_eddy_pipe.connect(dwi_mask, 'out_file', dwi_bias_correct, 'in_mask')

    elif eddy_method=="jac":
        dwi_mask = pe.Node(interface=umrt.BrainMask(), name="dwi_mask")
        dwi_mask.inputs.out_file = "brainmask.nii.gz"
        post_eddy_pipe.connect(tuple_rotated_bvec, 'tuple_elem', dwi_mask, 'grad_fsl')
        post_eddy_pipe.connect(abs_eddy, 'out_file' , dwi_mask, 'in_file')

        # dwi_bias_correct
        dwi_bias_correct = pe.Node(interface=mrt.DWIBiasCorrect(),
                                   name="dwi_bias_correct")
        dwi_bias_correct.inputs.use_ants = True

        post_eddy_pipe.connect(tuple_rotated_bvec, 'tuple_elem', dwi_bias_correct, 'grad_fsl')
        post_eddy_pipe.connect(abs_eddy, 'out_file', dwi_bias_correct, 'in_file')
        post_eddy_pipe.connect(dwi_mask, 'out_file', dwi_bias_correct, 'in_mask')


    # final dti fit
    final_dtifit = pe.Node(interface=dti.DTIFit(), name="final_dtifit")

    post_eddy_pipe.connect(dwi_bias_correct, 'out_file', final_dtifit, 'dwi')
    post_eddy_pipe.connect(dwi_mask, 'out_file', final_dtifit, 'mask')
    post_eddy_pipe.connect(inputnode, 'rotated_bvecs', final_dtifit, 'bvecs')
    post_eddy_pipe.connect(inputnode, 'bvals', final_dtifit, 'bvals')

    return post_eddy_pipe

################################ Inputs #############################################

def create_infosource():
    infosource = pe.Node(interface=niu.IdentityInterface(fields=['subject_id','session']), name="infosource")
    infosource.iterables = [('subject_id', subject_ids),('session',func_sessions)]
    return infosource

def create_datasource():
   datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id','session'],outfields=['dwi_AP','bval_AP','bvec_AP' 'json_AP', 'dwi_PA','bval_PA','bvec_PA' 'json_PA', 'T1w']),name = 'datasource')
   datasource.inputs.base_directory = data_path
   datasource.inputs.template = 'sub-%s/ses-%s/%s/sub-%s_ses-%s*%s'
   datasource.inputs.template_args = dict(
       dwi_AP=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-AP_dwi.nii.gz"]],
       bval_AP=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-AP_dwi.bval"]],
       bvec_AP=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-AP_dwi.bvec"]],
       json_AP=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-AP_dwi.json"]],

       dwi_PA=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-PA_dwi.nii.gz"]],
       bval_PA=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-PA_dwi.bval"]],
       bvec_PA=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-PA_dwi.bvec"]],
       json_PA=[['subject_id','session',"dwi", 'subject_id', 'session',"_dir-PA_dwi.json"]],

       T1w=[['subject_id','session',"anat", 'subject_id', 'session',"_T1w.nii.gz"]]
       )
   datasource.inputs.sort_filelist = True
   return datasource


def create_main_workflow():
    main_workflow = pe.Workflow(name= main_wf_name)
    main_workflow.base_dir = nipype_analyses_path

    ## Infosource
    infosource = create_infosource()

    ## Data source
    datasource = create_datasource()

    main_workflow.connect(infosource, 'subject_id', datasource, 'subject_id')
    main_workflow.connect(infosource, 'session', datasource, 'session')

    ############################################# Preprocessing ################################
    print('create_preprocess_dwi')

    if len(reorient_dims):

        reorient_pipe = create_reorient_pipe(reorient_dims)

        main_workflow.connect(datasource, 'dwi_AP', reorient_pipe, 'inputnode.dwi_AP')
        main_workflow.connect(datasource, 'dwi_PA', reorient_pipe, 'inputnode.dwi_PA')
        main_workflow.connect(datasource, 'T1w', reorient_pipe, 'inputnode.T1w')

        preprocess_dwi_pipe = create_preprocess_dwi_pipe()

        main_workflow.connect(reorient_pipe, 'outputnode.reoriented_dwi_AP', preprocess_dwi_pipe, 'inputnode.dwi_AP')
        main_workflow.connect(datasource, 'bval_AP', preprocess_dwi_pipe, 'inputnode.bval_AP')
        main_workflow.connect(datasource, 'bvec_AP', preprocess_dwi_pipe, 'inputnode.bvec_AP')

        main_workflow.connect(reorient_pipe, 'outputnode.reoriented_dwi_PA', preprocess_dwi_pipe, 'inputnode.dwi_PA')
        main_workflow.connect(datasource, 'bval_PA', preprocess_dwi_pipe, 'inputnode.bval_PA')
        main_workflow.connect(datasource, 'bvec_PA', preprocess_dwi_pipe, 'inputnode.bvec_PA')

    else:

        preprocess_dwi_pipe = create_preprocess_dwi_pipe()

        main_workflow.connect(datasource, 'dwi_AP',  preprocess_dwi_pipe, 'inputnode.dwi_AP')
        main_workflow.connect(datasource, 'bval_AP', preprocess_dwi_pipe, 'inputnode.bval_AP')
        main_workflow.connect(datasource, 'bvec_AP', preprocess_dwi_pipe, 'inputnode.bvec_AP')

        main_workflow.connect(datasource, 'dwi_PA',  preprocess_dwi_pipe, 'inputnode.dwi_PA')
        main_workflow.connect(datasource, 'bval_PA', preprocess_dwi_pipe, 'inputnode.bval_PA')
        main_workflow.connect(datasource, 'bvec_PA', preprocess_dwi_pipe, 'inputnode.bvec_PA')

    # acq_pipe
    #print("acq_pipe")
    #acq_pipe = create_acq_pipe()

    print("acq_pipe")
    acq_pipe = create_mean_acq_pipe()

    main_workflow.connect(datasource, 'json_AP', acq_pipe, 'inputnode.json_AP')
    main_workflow.connect(datasource, 'json_PA', acq_pipe, 'inputnode.json_PA')

    main_workflow.connect(datasource, 'bval_AP', acq_pipe, 'inputnode.bval_AP')
    main_workflow.connect(datasource, 'bval_PA', acq_pipe, 'inputnode.bval_PA')

    # topup_pipe
    #print("topup_pipe")
    #topup_pipe = create_topup_pipe()

    print("topup_mean_pipe")
    topup_pipe = create_mean_topup_pipe()

    main_workflow.connect(datasource, 'bvec_AP', topup_pipe, 'inputnode.bvec_AP')
    main_workflow.connect(datasource, 'bvec_PA', topup_pipe, 'inputnode.bvec_PA')

    main_workflow.connect(preprocess_dwi_pipe, 'outputnode.preproc_dwi_AP', topup_pipe, 'inputnode.dwi_AP')
    main_workflow.connect(preprocess_dwi_pipe, 'outputnode.preproc_dwi_PA', topup_pipe, 'inputnode.dwi_PA')

    main_workflow.connect(acq_pipe, 'acq.bval_AP_new_file', topup_pipe, 'inputnode.bval_AP_new_file')
    main_workflow.connect(acq_pipe, 'acq.bval_PA_new_file', topup_pipe, 'inputnode.bval_PA_new_file')
    main_workflow.connect(acq_pipe, 'acq.acq_param_file', topup_pipe, 'inputnode.acq_param_file')

    # eddy_pipe
    print("eddy_pipe")
    eddy_pipe = create_eddy_pipe(eddy_method=eddy_method)

    main_workflow.connect(datasource, 'bvec_AP', eddy_pipe, 'inputnode.bvec_AP')
    main_workflow.connect(datasource, 'bvec_PA', eddy_pipe, 'inputnode.bvec_PA')

    main_workflow.connect(acq_pipe, 'acq.bval_AP_new_file', eddy_pipe, 'inputnode.bval_AP_new_file')
    main_workflow.connect(acq_pipe, 'acq.bval_PA_new_file', eddy_pipe, 'inputnode.bval_PA_new_file')
    main_workflow.connect(acq_pipe, 'acq.acq_param_file', eddy_pipe, 'inputnode.acq_param_file')
    main_workflow.connect(acq_pipe, 'acq.acq_index_file', eddy_pipe, 'inputnode.acq_index_file')

    main_workflow.connect(preprocess_dwi_pipe, 'outputnode.preproc_dwi_AP', eddy_pipe, 'inputnode.dwi_AP')
    main_workflow.connect(preprocess_dwi_pipe, 'outputnode.preproc_dwi_PA', eddy_pipe, 'inputnode.dwi_PA')

    main_workflow.connect(topup_pipe, 'topup.out_movpar', eddy_pipe, 'inputnode.topup_movpar')
    main_workflow.connect(topup_pipe, 'topup.out_fieldcoef', eddy_pipe, 'inputnode.topup_fieldcoef')
    main_workflow.connect(topup_pipe, 'mask_unwarped_b0.out_file', eddy_pipe, 'inputnode.b0_mask')

    # post_eddy_pipe
    print("post_eddy_pipe")
    post_eddy_pipe = create_post_eddy_pipe(eddy_method=eddy_method)

    main_workflow.connect(eddy_pipe, 'eddy.out_corrected', post_eddy_pipe, 'inputnode.dwi_corrected')
    main_workflow.connect(eddy_pipe, 'paste_bval.paste_file', post_eddy_pipe, 'inputnode.bvals')
    main_workflow.connect(eddy_pipe, 'eddy.out_rotated_bvecs', post_eddy_pipe, 'inputnode.rotated_bvecs')

    return main_workflow

if __name__ =='__main__':

    ### main_workflow
    wf = create_main_workflow()
    wf.config['execution'] = {'remove_unnecessary_outputs':'false'}
    wf.write_graph(graph2use="colored")

    wf.run(plugin='MultiProc', plugin_args={'n_procs' : 8})
