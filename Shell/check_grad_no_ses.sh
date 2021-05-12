#!/bin/bash

# script to check gradient orientation and correct for it if necessary
# call bash script using : >> bash check_grad_no_ses.sh

# script written originally by Lucile Brun, adapted by Julien Sein (julien.sein@univ-amu.fr)
# Institut de Neurosciences de la Timone, Marseille, France
#version of April 29th 2021

####### To be edited by user #####
##################################

study='Aging'
base_dir=/home/seinj/mygpdata/MRI_BIDS_DATABANK/${study} # path to the BIDS folder of your study
base_output_dir=dwi_prep_newden # name of the folder that will be created in derivatives
# where the preproc data will be stored
#list_sub=$(ls -d $base_dir/sub*) # to select all subjects from the BIDS folder.
list_sub='01' #ex: '01 02 03'

#################################
###### end of edition ###########


for subi in $list_sub
do

sub="sub-${subi}"
#sub1=$(echo ${subi##*/})
#sub=$(echo ${sub1%_*})


echo "----starting ${sub}----"

LC_NUMERIC="en_US.UTF-8"
in_dir=${base_dir}/${sub}/dwi
t1_dir=${base_dir}/${sub}/anat
out_dir=${base_dir}/derivatives/$base_output_dir/${sub}

mkdir -p $out_dir/topup
cp slspec.txt $out_dir/topup/.

AP=${in_dir}/${sub}${acq}_dir-AP_dwi.nii.gz
PA=${in_dir}/${sub}${acq}_dir-PA_dwi.nii.gz
AP_bval=${in_dir}/${sub}${acq}_dir-AP_dwi.bval
PA_bval=${in_dir}/${sub}${acq}_dir-PA_dwi.bval
AP_bvec=${in_dir}/${sub}${acq}_dir-AP_dwi.bvec
PA_bvec=${in_dir}/${sub}${acq}_dir-PA_dwi.bvec


t1=$t1_dir/${sub}_T1w.nii.gz

readout_time=$(cat "$in_dir/${sub}${acq}_dir-AP_dwi.json" | python -c "import sys, json; print(json.load(sys.stdin)['TotalReadoutTime'])" )
echo_spacing=$(cat "$in_dir/${sub}${acq}_dir-AP_dwi.json" | python -c "import sys, json; print(json.load(sys.stdin)['EffectiveEchoSpacing'])")
slice_times=$(cat "$in_dir/${sub}${acq}_dir-AP_dwi.json" | python -c "import sys, json; print(json.load(sys.stdin)['SliceTiming'])" )
#mb_factor=$(cat "$in_dir/${sub}_dir-AP_dwi.json" | python -c "import sys, json; print(json.load(sys.stdin)['MultibandAccelerationFactor'])")


echo "variables are set"

mkdir -p $out_dir/test_gradorient

echo "########################################"
echo "### Prepare, check and reorient data ###"
echo "########################################"

## prepare check and reorient data to MNI152 standard
echo "Reorient data to the MNI152 standard"
fslreorient2std "$AP" "${out_dir}/AP_rts.nii.gz"
fslreorient2std "$PA" "${out_dir}/PA_rts.nii.gz"
fslreorient2std "$t1" "${out_dir}/t1_rts.nii.gz"

####################################################################

echo "Change orientation into RAS+" #(first data and then header)
fslswapdim "${out_dir}/AP_rts.nii.gz" -x y z "${out_dir}/AP_rts_RAS.nii.gz"
fslorient -swaporient "${out_dir}/AP_rts_RAS.nii.gz"
fslswapdim "${out_dir}/PA_rts.nii.gz" -x y z "${out_dir}/PA_rts_RAS.nii.gz"
fslorient -swaporient "${out_dir}/PA_rts_RAS.nii.gz"
fslswapdim "${out_dir}/t1_rts.nii.gz" -x y z "${out_dir}/t1_rts_RAS.nii.gz"
fslorient -swaporient "${out_dir}/t1_rts_RAS.nii.gz"

###################################################################
echo "denoise and degibbs" 
dwidenoise "${out_dir}/PA_rts_RAS.nii.gz" "${out_dir}/PA_rts_RAS_den.nii.gz"
dwidenoise "${out_dir}/AP_rts_RAS.nii.gz" "${out_dir}/AP_rts_RAS_den.nii.gz"

mrdegibbs "${out_dir}/PA_rts_RAS_den.nii.gz" "${out_dir}/PA_rts_RAS_den_unr.nii.gz" -axes 0,1
mrdegibbs "${out_dir}/AP_rts_RAS_den.nii.gz" "${out_dir}/AP_rts_RAS_den_unr.nii.gz" -axes 0,1
###################################################################

echo "Copy bval,bvec files"
cp $AP_bval ${out_dir}/AP.bval
cp $AP_bvec ${out_dir}/AP.bvec
cp $PA_bval ${out_dir}/PA.bval
cp $PA_bvec ${out_dir}/PA.bvec


####################################################################

echo "Extract first b0 volume"
fslroi "${out_dir}/AP_rts_RAS_den_unr.nii.gz" "${out_dir}/AP_rts_RAS_den_unr_b0.nii.gz" 0 1
bet "${out_dir}/AP_rts_RAS_den_unr_b0.nii.gz" "${out_dir}/test_gradorient/AP_rts_RAS_den_unr_b0_brain.nii.gz" -m -f 0.3
#fsleyes ${out_dir}/AP_rts_RAS_b0.nii.gz ${out_dir}/test_gradorient/AP_rts_RAS_b0_brain_mask.nii.gz

####################################################################

echo "Check diffusion gradients orientation"

echo "tensor fitting"
dtifit -k "${out_dir}/AP_rts_RAS_den_unr.nii.gz" -o "${out_dir}/test_gradorient/dti" -m "${out_dir}/test_gradorient/AP_rts_RAS_den_unr_b0_brain_mask.nii.gz" -r "${out_dir}/AP.bvec" -b "${out_dir}/AP.bval" -V
#fsleyes ${out_dir}/test_gradorient/dti_FA.nii.gz  ${out_dir}/test_gradorient/dti_V1.nii.gz

echo "if needed, reorient bvecs"
if [ -e ${out_dir}/AP.bvec ] ; then
rm ${out_dir}/AP.bvec
fi
rXs=;rYs=;rZs=;Xs=;Ys=;Zs=;
volumes=$(head -1 $AP_bvec | wc -w)
Xs=$(cat $AP_bvec | head -1 | tail -1)
Ys=$(cat $AP_bvec | head -2 | tail -1)
Zs=$(cat $AP_bvec | head -3 | tail -1)
i=1
while [ $i -le $volumes ] ; do
X=$(echo $Xs | cut -d " " -f "$i")
Y=$(echo $Ys | cut -d " " -f "$i")
Z=$(echo $Zs | cut -d " " -f "$i")
X=$(tr -dc '[[:print:]]' <<< "$X")
Y=$(tr -dc '[[:print:]]' <<< "$Y")
Z=$(tr -dc '[[:print:]]' <<< "$Z")
rX=$(echo "-1 * $X" | bc -l | sed 's/^\./0./' | sed 's/^-\./-0./') #example were x is flipped
rY=$(echo " 1 * $Y" | bc -l | sed 's/^\./0./' | sed 's/^-\./-0./')
rZ=$(echo " 1 * $Z" | bc -l | sed 's/^\./0./' | sed 's/^-\./-0./')
rX=$(printf "%1.7f" $rX)
rY=$(printf "%1.7f" $rY)
rZ=$(printf "%1.7f" $rZ)
rXs=${rXs}${rX}" ";
rYs=${rYs}${rY}" ";
rZs=${rZs}${rZ}" ";
i=$(echo "$i + 1" | bc);
done
echo "$rXs" >> ${out_dir}/AP.bvec;
echo "$rYs" >> ${out_dir}/AP.bvec;
echo "$rZs" >> ${out_dir}/AP.bvec;
cp ${out_dir}/AP.bvec ${out_dir}/PA.bvec


dtifit -k "${out_dir}/AP_rts_RAS_den_unr.nii.gz" -o "${out_dir}/test_gradorient/dti" -m "${out_dir}/test_gradorient/AP_rts_RAS_den_unr_b0_brain_mask.nii.gz" -r "${out_dir}/AP.bvec" -b "${out_dir}/AP.bval" -V
fsleyes ${out_dir}/test_gradorient/dti_FA.nii.gz  ${out_dir}/test_gradorient/dti_V1.nii.gz

#rm -p ${out_dir}/test_gradorient/*
#rmdir ${out_dir}/test_gradorient

####################################################################