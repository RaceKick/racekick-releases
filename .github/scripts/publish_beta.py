"""Release bridge: only tested installer binaries, never private app source."""
import hashlib,json,os,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def gh(*args):return subprocess.check_output(['gh',*args],text=True)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(value,message):
 if not value:raise RuntimeError(message)
def main():
 repo=os.environ['GITHUB_REPOSITORY'];require(repo=='RaceKick/racekick-releases','Wrong repository')
 manifest=json.loads((ROOT/'transfer/manifest.json').read_text());version=manifest['version'];require(re.fullmatch(r'0\.1\.\d+',version),'Invalid beta version');tag='v'+version+'-beta'
 require(os.environ['GITHUB_REF_NAME']=='release-upload/'+version,'Transfer branch/version mismatch')
 require(re.fullmatch(r'[0-9a-f]{40}',manifest['source_commit']),'Invalid tested source commit')
 out=ROOT/'assembled';out.mkdir(exist_ok=True);archive=out/'tested-artifact.zip'
 with archive.open('wb') as target:
  for i,entry in enumerate(manifest['parts']):
   require(entry['name']==f'part-{i:03d}.bin','Unexpected transfer path');p=ROOT/'transfer'/entry['name'];require(digest(p)==entry['sha256'],'Transfer part hash mismatch');target.write(p.read_bytes())
 require(digest(archive)==manifest['artifact_sha256'],'Artifact hash mismatch')
 installer='RaceKick-Setup-'+version+'-Beta.exe';names={installer,'SHA256SUMS.txt','build-info.json','installed-smoke.json','upgrade-smoke.json'}
 with zipfile.ZipFile(archive) as z:
  require(set(z.namelist())==names,'Artifact contains unexpected files')
  for name in names:
   info=z.getinfo(name);require(info.file_size<500*1024*1024,'Asset too large');(out/name).write_bytes(z.read(name))
 smoke=json.loads((out/'installed-smoke.json').read_text());upgrade=json.loads((out/'upgrade-smoke.json').read_text());info=json.loads((out/'build-info.json').read_text())
 require(smoke.get('ok') is True and smoke.get('frozen') is True and smoke.get('native_overlays')==6 and smoke.get('stream_sources')==7,'Installed-app test did not pass')
 require(upgrade.get('ok') is True and upgrade.get('to_version')==version and all(upgrade.get(k) is True for k in ('same_install_directory','settings_preserved','driver_tags_notes_preserved','custom_image_preserved','uninstall_keeps_data')),'Upgrade/data preservation did not pass')
 require(info.get('version')==version and info.get('source_commit')==manifest['source_commit'] and info.get('installer')==installer,'Build identity mismatch')
 checksum=digest(out/installer);require(checksum==info['sha256'] and (out/'SHA256SUMS.txt').read_text().split()==[checksum,installer],'Installer checksum mismatch')
 require((out/installer).read_bytes()[:2]==b'MZ','Not a Windows installer')
 notes=ROOT/'transfer/release-notes.md';notes.write_text(manifest['notes'])
 records=json.loads(gh('api','repos/'+repo+'/releases?per_page=100'));existing=next((r for r in records if r['tag_name']==tag),None)
 if existing:require(existing['draft'],'Refusing to overwrite a published release')
 else:gh('release','create',tag,'--repo',repo,'--target','main','--draft','--prerelease','--title','RaceKick '+version+' Beta','--notes-file',str(notes))
 gh('release','upload',tag,str(out/installer),str(out/'SHA256SUMS.txt'),str(out/'build-info.json'),'--repo',repo,'--clobber')
 release=next(r for r in json.loads(gh('api','repos/'+repo+'/releases?per_page=100')) if r['tag_name']==tag);asset=next((a for a in release['assets'] if a['name']==installer),None)
 require(asset is not None and asset.get('state')=='uploaded' and asset.get('digest')=='sha256:'+checksum,'GitHub asset digest verification failed')
 gh('release','edit',tag,'--repo',repo,'--draft=false','--prerelease','--notes-file',str(notes))
 print('Published '+tag+'; installer SHA256 '+checksum)
if __name__=='__main__':main()
