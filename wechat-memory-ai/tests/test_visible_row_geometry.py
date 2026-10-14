"""A one-physical-pixel bottom overhang may only yield an enclosed analysis region."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class VisibleRowGeometryTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows compiler required')
    def test_crop_is_limited_to_one_bottom_pixel_and_rechecks_every_geometry_gate(self):
        # Tests the rectangle used by production Analyze. No native bitmap or
        # window is created; existing excluded native tests remain skipped.
        expected = dict(
            contained='valid/10,248,600,72', bottom_one='valid/10,249,600,71',
            observed_scaled='valid/10,237,600,83', bottom_two='row_outside_list/empty',
            top_one='row_outside_list/empty', left_one='row_outside_list/empty',
            right_one='row_outside_list/empty', top_and_bottom='row_outside_list/empty',
            outside_below='row_outside_list/empty', visible_minimum='valid/10,284,600,36',
            visible_too_short='row_height_below_minimum/empty', scaled_minimum='valid/10,266,600,54',
            scaled_too_short='row_height_below_minimum/empty', left_misaligned='row_left_misaligned/empty',
            right_misaligned='row_right_misaligned/empty', narrow='row_width_below_minimum/empty',
            list_outside='list_outside_frame/empty', missing_image='image_missing/empty',
            bad_scale='scale_invalid/empty', empty_list='list_size_invalid/empty',
            low_dpi_one='valid/10,249,600,71', high_dpi_one='row_height_below_minimum/empty',
            high_dpi_two='row_outside_list/empty',
        )
        root = Path(__file__).resolve().parents[1]
        framework = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319'
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory)/'visible-row.exe'
            command = [str(framework/'csc.exe'), '/nologo', '/target:exe', '/out:'+str(executable),
                       '/reference:'+str(framework/'System.Drawing.dll'),
                       str(root/'src/wechat_memory/visual_direction.cs'), str(root/'tests/fixtures/visible_row_contract.cs')]
            compiled = subprocess.run(command,capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode(errors='replace'))
            done = subprocess.run([str(executable)],capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(done.returncode,0,done.stderr.decode(errors='replace'))
            self.assertEqual(dict(line.split('=',1) for line in done.stdout.decode().splitlines()),expected)
