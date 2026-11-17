"""Choose an explicitly frozen study baseline or the current working PCB."""
import hashlib,json,os

def load_source(study_dir):
 if os.environ.get('PHOENIX_PHY_FROZEN_BASELINE')=='1':
  folder=study_dir.parent/'phy-compact-inductor/baseline'
  cp=json.loads((folder/'checkpoint.json').read_text());board=folder/cp['board']
 else:
  cp=json.loads((study_dir/'working-candidate.json').read_text());board=study_dir/cp['board']
 assert hashlib.sha256(board.read_bytes()).hexdigest()==cp['sha256']
 return cp,board
