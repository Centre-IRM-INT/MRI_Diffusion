#!/bin/bash

# script to preprocess diffusion weighted images
# call bash script using : >> bash dwiprep_no_ses.sh
# if ni cuda, comment the paragraph dedicated to cuda

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
acq= # add something if this flag is present in the scan name: ex: acq='_acq-1mm'
smooth=1 ## value of smoothing kernel used with fslmaths in the smoothing part at the end of the script.
bias_method='fsl' # 'fsl' or 'ants' (ants recommended but need to have ants installed)

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
#fsleyes ${out_dir}/test_gradorient/dti_FA.nii.gz  ${out_dir}/test_gradorient/dti_V1.nii.gz

#rm -p ${out_dir}/test_gradorient/*
#rmdir ${out_dir}/test_gradorient

####################################################################

echo "Split 4D volume"
if ! [ -d ${out_dir}/split_AP_volumes ]; then
mkdir ${out_dir}/split_AP_volumes
fi
if ! [ -d ${out_dir}/split_PA_volumes ]; then
mkdir ${out_dir}/split_PA_volumes
fi
if ! [ "$(ls -A ${out_dir}/split_AP_volumes)" ]; then
fslsplit ${out_dir}/AP_rts_RAS_den_unr.nii.gz ${out_dir}/split_AP_volumes/vol_ -t
fi
if ! [ "$(ls -A ${out_dir}/split_PA_volumes)" ]; then
fslsplit ${out_dir}/PA_rts_RAS_den_unr.nii.gz ${out_dir}/split_PA_volumes/vol_ -t
fi


echo "##############################################################"
echo "### Full distortion correction using FSL 'topup/eddy' tool ###"
echo "##############################################################"

# call bash script using "full" or "b0" mode as argument
# differences in code lines are marked ***

#ARGS=1
#if [ $# -ne $ARGS ]
#then
#   echo "Usage: `basename $0` [mode]"
#   echo
#   echo "[mode]     'full' or 'b0' to use full sequence with opposed PE or only b0 volumes"
#   echo
#   exit 1
#fi

#mode=$1

if [ -e ${out_dir}/AP.bvec ] && [ -e ${out_dir}/PA.bvec ]
then
    mode='full'
else
    mode='b0'
fi

if [ $mode = "full" ]; then
    echo "!!!!!!! mode is \"full\" and resampling will be 'lsr' !!!!!!!!"
else
    echo "!!!!!!! mode is not \"full\" and resampling will be 'jac'  !!!!!!!!"
fi

####################################################################

mkdir -p $out_dir/topup
if [ -f $out_dir/topup/acq_parameters ]; then
    rm $out_dir/topup/acq_parameters
fi
if [ -f $out_dir/topup/acq_index ]; then
    rm $out_dir/topup/acq_index
fi
if [ -f $out_dir/topup/topup_bval ]; then
    rm $out_dir/topup/topup_bval
fi
if [ -f $out_dir/topup/topup_bvec ]; then
    rm $out_dir/topup/topup_bvec
fi

bval=$out_dir/PA.bval
bvec=$out_dir/PA.bvec

####################################################################

# Intensity Normalisation across Series (to ensure consistency across baseline intensities)

####################################################################

echo "Extract blip-up and blip-down b0 volumes"
echo "And create acquisition parameters and corresponding index files"
range=50 # acceptance range around b-value, if effective value is given by scanner
count_b0=0
i=1
echo "- blip-up phase encoding"
for b in $(cat $bval)
do
    index=$(printf '%04d' `expr $i - 1`) # zero padding for index of splitted volume, starting at 0000
    
    if [ "$b" -gt `expr 0 - $range` ] && [ "$b" -lt `expr 0 + $range` ]; then
        cp $out_dir/split_PA_volumes/vol_$index.nii.gz $out_dir/split_PA_volumes/b0vol_$index.nii.gz
        count_b0=`expr $count_b0 + 1`
        echo "0 1 0 $readout_time" >> $out_dir/topup/acq_parameters
    fi
    
    echo $count_b0 "" >> $out_dir/topup/acq_index
    
    i=`expr $i + 1`
    
done

nvol_up=`expr $count_b0 + 1` # used to apply topup later on

echo "- blip-down phase encoding"
i=1
for b in $(cat $bval)
do
    index=$(printf '%04d' `expr $i - 1`) # zero padding for index of splitted volume, starting at 0000
    
    if [ "$b" -gt `expr 0 - $range` ] && [ "$b" -lt `expr 0 + $range` ]; then
        cp $out_dir/split_AP_volumes/vol_$index.nii.gz $out_dir/split_AP_volumes/b0vol_$index.nii.gz
        count_b0=`expr $count_b0 + 1`
        echo "0 -1 0 $readout_time" >> $out_dir/topup/acq_parameters
    fi
    
    # ***
   if [ $mode = "full" ]; then
        echo  $count_b0 "" >> $out_dir/topup/acq_index
  fi
    # ***
    
    i=`expr $i + 1`
    
done
echo ""

####################################################################

echo "Merge blip-up and blip-down data"
fslmerge -t $out_dir/topup/up_b0.nii.gz `${FSLDIR}/bin/imglob $out_dir/split_PA_volumes/b0vol_????.nii.gz`
fslmerge -t $out_dir/topup/down_b0.nii.gz `${FSLDIR}/bin/imglob $out_dir/split_AP_volumes/b0vol_????.nii.gz`
fslmerge -t $out_dir/topup/up_down_b0.nii.gz $out_dir/topup/up_b0.nii.gz $out_dir/topup/down_b0.nii.gz
rm $out_dir/topup/up_b0.nii.gz
rm $out_dir/topup/down_b0.nii.gz

if [ $mode = "full" ]; then
# create a bval and bvec file with twice as many values/directions and be sure to remove the ^M character added in the paste procedure
fslmerge -t $out_dir/topup/up_down_data.nii.gz $out_dir/PA_rts_RAS_den_unr.nii.gz $out_dir/AP_rts_RAS_den_unr.nii.gz
    paste $bval $bval > $out_dir/topup/topup_bval
    perl -p -e 's/\r//g' $out_dir/topup/topup_bval > $out_dir/topup/test
    cat $out_dir/topup/test > $out_dir/topup/topup_bval
    paste $out_dir/PA.bvec $out_dir/PA.bvec > $out_dir/topup/topup_bvec
else
    cp $out_dir/PA_rts_RAS_den_unr.nii.gz $out_dir/topup/up_down_data.nii.gz
    paste $bval > $out_dir/topup/topup_bval
    paste $out_dir/PA.bvec > $out_dir/topup/topup_bvec
fi


####################################################################

# OLD: Correct for EVEN number of slices to use b02b0.cnf
#dimz=`fslval $out_dir/topup/up_down_b0.nii.gz dim3`
#mboff=0 # by default we assume even number of slices and no removal
#if [ `expr $dimz % 2` -eq 1 ]; then
#    echo "Remove one slice from data to get even number of slices"
#    mboff=-1 #removal from the bottom slice by fslroi below
#    fslroi $out_dir/topup/up_down_b0.nii.gz $out_dir/topup/up_down_b0.nii.gz 0 -1 0 -1 1 -1
#    fslroi $out_dir/topup/up_down_data.nii.gz $out_dir/topup/up_down_data.nii.gz 0 -1 0 -1 1 -1
#    fslroi $out_dir/split_PA_volumes/vol_0000.nii.gz $out_dir/topup/up_b0.nii.gz 0 -1 0 -1 1 -1
#    fslroi $out_dir/split_PA_volumes/vol_0000.nii.gz $out_dir/topup/down_b0.nii.gz 0 -1 0 -1 1 -1
#fi
    
####################################################################

echo "Estimation of the susceptibility off-resonance field..."
if [ `expr $dimz % 2` -eq 1 ]; then
     echo "odd number of slices: run topup with specific config file"
     topup --imain="${out_dir}/topup/up_down_b0.nii.gz" --datain="${out_dir}/topup/acq_parameters" --config=b02b0_oddslices.cnf  --out="${out_dir}/topup/topup" --iout="${out_dir}/topup/up_down_b0_unwarped.nii.gz" --fout="${out_dir}/topup/topup_fieldmap" -v
else
    echo "even number of slices: run topup with standard config file"
    topup --imain="${out_dir}/topup/up_down_b0.nii.gz" --datain="${out_dir}/topup/acq_parameters" --config=b02b0.cnf  --out="${out_dir}/topup/topup" --iout="${out_dir}/topup/up_down_b0_unwarped.nii.gz" --fout="${out_dir}/topup/topup_fieldmap" -v
fi
fslmaths $out_dir/topup/up_down_b0_unwarped.nii.gz -Tmean $out_dir/topup/topup_b0_mean.nii.gz

bet $out_dir/topup/topup_b0_mean.nii.gz $out_dir/topup/topup_b0_mean_brain.nii.gz -m -f 0.3

fslmaths $out_dir/topup/topup_b0_mean_brain -thr 0 -bin $out_dir/topup/topup_b0_mean_brain_mask

echo "Eddy-current estimation and complete correction..."
# TIP: see if eddy_cuda or eddy.gpu is available

if [ $mode = "full" ]; then
    resamp='lsr'
else
    resamp='jac'
fi

### calculate the file slspec.txt using matlab. Comment if you calculate this file outside of the script:

#APjson=${AP/nii.gz/json}
#APjson_short=$(echo $APjson | sed 's:.*/::')
#matlab -nosplash -nodisplay -r "cd ~/Documents/MATLAB/m/eddy;create_slspec("\'$APjson\',\'$out_dir/topup/slspec.txt\'")" > /dev/null

### for user with no acces to eddy_cuda:

eddy_openmp --imain=$out_dir/topup/up_down_data.nii.gz --mask=$out_dir/topup/topup_b0_mean_brain_mask.nii.gz --acqp=$out_dir/topup/acq_parameters --index=$out_dir/topup/acq_index --bvecs=$out_dir/topup/topup_bvec --bvals=$out_dir/topup/topup_bval --topup=$out_dir/topup/topup --out=$out_dir/topup/topup_eddy --flm=quadratic --slm=none --fwhm=0,0,0,0,0 --niter=5 --fep --interp=spline --resamp=$resamp --nvoxhp=1000 --ff=10 --dont_peas --data_is_shelled --residuals  --cnr_maps --repol --ol_type=gw --slspec=$out_dir/topup/slspec.txt --estimate_move_by_susceptibility  -v

### eddy_cuda with slice-2-volume registration and group-wise outlier replacement

#eddy_cuda --imain=$out_dir/topup/up_down_data.nii.gz --mask=$out_dir/topup/topup_b0_mean_brain_mask.nii.gz --acqp=$out_dir/topup/acq_parameters --index=$out_dir/topup/acq_index --bvecs=$out_dir/topup/topup_bvec --bvals=$out_dir/topup/topup_bval --topup=$out_dir/topup/topup --out=$out_dir/topup/topup_eddy --flm=quadratic --slm=none --fwhm=0,0,0,0,0 --niter=5 --fep --interp=spline --resamp=$resamp --nvoxhp=1000 --ff=10 --dont_peas --data_is_shelled --residuals  --cnr_maps --repol --ol_type=gw  --mporder=4 --s2v_niter=5 --s2v_lambda=1 --s2v_interp=trilinear --slspec=$out_dir/topup/slspec.txt --estimate_move_by_susceptibility  -v


echo "Correct for negative values"
mv $out_dir/topup/topup_eddy.nii.gz $out_dir/topup/topup_eddy_orig.nii.gz
fslmaths $out_dir/topup/topup_eddy_orig.nii.gz -abs $out_dir/topup/topup_eddy.nii.gz

echo "Change corrected bvec name"
cat $out_dir/topup/topup_eddy.eddy_rotated_bvecs > $out_dir/topup/topup_bvec

echo "create individual QC report with eddy_quad"

if [ $mode = "full" ]
then
   mv $out_dir/topup/topup_eddy.nii.gz $out_dir/topup/topup_eddy_lsr.nii.gz
    fslmerge -t $out_dir/topup/topup_eddy.nii.gz $out_dir/topup/topup_eddy_lsr.nii.gz $out_dir/topup/topup_eddy_lsr.nii.gz
fi
rm -r ${out_dir}/topup/quad

eddy_quad ${out_dir}/topup/topup_eddy -idx ${out_dir}/topup/acq_index -par ${out_dir}/topup/acq_parameters -m ${out_dir}/topup/topup_b0_mean_brain_mask.nii.gz -b ${out_dir}/topup/topup_bval -o ${out_dir}/topup/quad -g ${out_dir}/topup/topup_bvec -f ${out_dir}/topup/topup_fieldmap.nii.gz -s "$out_dir/topup/${APjson_short/dwi.json/slspec.txt}"

###create brain mask with mrtrix

dwi2mask $out_dir/topup/topup_eddy.nii.gz $out_dir/topup/eddy_brain_mask_mrtrix.nii.gz

## Bias correction with mrtrix. If ants is installed, use ('ants') for correction (recommended), if not use FSL-fast ('fsl')

dwibiascorrect $bias_method $out_dir/topup/topup_eddy.nii.gz $out_dir/topup/topup_eddy_unbiased.nii.gz -fslgrad ${out_dir}/topup/topup_bvec ${out_dir}/topup/topup_bval -bias ${out_dir}/topup/bias.nii.gz -mask $out_dir/topup/eddy_brain_mask_mrtrix.nii.gz

## smooth with gaussian kernel of $sigma ( FSL-fslmaths)

fslmaths $out_dir/topup/topup_eddy_unbiased.nii.gz -kernel gauss $sigma -fmean $out_dir/topup/topup_eddy_unbiased_smooth.nii.gz


bvec=

done

### for group QA with eddyqc:

# for sub ...
#do
#if [ -e $out_dir/topup/quad ] ; then
#echo -e $out_dir/topup/quad >> $group_dir/qc_folders.txt
#fi

#done

#rm -r $group_dir/squad
#eddy_squad $group_dir/qc_folders.txt -u -o  $group_dir/squad
