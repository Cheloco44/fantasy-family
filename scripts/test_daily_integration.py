"""Parent integration gates for a usable Pages subpath build."""
from pathlib import Path
import unittest,subprocess
class Integration(unittest.TestCase):
 def test_daily_build_has_pages_base_and_no_telemetry(self):
  text=Path('.github/workflows/daily-clubhouse.yml').read_text()
  build=text.split('  build:\n',1)[1].split('  deploy:\n',1)[0]
  self.assertIn('BASE_PATH: /fantasy-family/',build)
  self.assertIn("ASTRO_TELEMETRY_DISABLED: '1'",build)
 def test_workflow_shell_blocks_parse_without_execution(self):
  lines=Path('.github/workflows/daily-clubhouse.yml').read_text().splitlines();blocks=[];i=0
  while i<len(lines):
   if lines[i].strip()=='run: |':
    indent=len(lines[i])-len(lines[i].lstrip());i+=1;body=[]
    while i<len(lines) and (not lines[i].strip() or len(lines[i])-len(lines[i].lstrip())>indent):
     body.append(lines[i][indent+2:]);i+=1
    blocks.append('\n'.join(body)+'\n')
   else:i+=1
  self.assertGreater(len(blocks),5)
  for n,body in enumerate(blocks):
   parsed=subprocess.run(['bash','-n'],input=body,text=True,capture_output=True)
   self.assertEqual(parsed.returncode,0,f'shell block {n} failed syntax validation')
if __name__=='__main__':unittest.main()
