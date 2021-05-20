"""
copied from https://stackoverrun.com/fr/q/6768689
seems was never wrapped in nipype
"""
import os

from nipype.interfaces.fsl.base import FSLCommand, FSLCommandInputSpec
from nipype.interfaces.base import (CommandLine, CommandLineInputSpec,
                                    TraitedSpec, File, traits)


# FslOrient
class FslOrientInputSpec(FSLCommandInputSpec):

    main_option = traits.Str(
        desc='main option', argstr='-%s', position=0, mandatory=True)

    code = traits.Int(
        argstr='%d', desc='code for setsformcode', position=1)

    in_file = File(
        exists=True, desc='input file', argstr='%s', position=2,
        mandatory=True)


class FslOrientOutputSpec(TraitedSpec):

    out_file = File(desc="out file", exists=True)


class FslOrient(FSLCommand):
    """
    copied and adapted from
    seems was never wrapped in nipype
    """
    _cmd = 'fslorient'
    input_spec = FslOrientInputSpec
    output_spec = FslOrientOutputSpec

    def _format_arg(self, name, spec, value):

        from nipype.utils.filemanip import split_filename as split_f
        from shutil import copyfile
        import os

        if name == 'in_file':
            # copy the file in local dir
            path, base, ext = split_f(value)
            new_file = os.path.abspath(base+ext)
            copyfile(value, new_file)

            value = new_file

        return super(FslOrient, self)._format_arg(name, spec, value)


    def _list_outputs(self):

        from nipype.utils.filemanip import split_filename as split_f
        import os

        outputs = self.output_spec().get()

        path, base, ext = split_f(self.inputs.in_file)
        outputs['out_file'] = os.path.abspath(base+ext)

        return outputs
