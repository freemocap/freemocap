from pathlib import Path
from tqdm import tqdm
import subprocess

def clone_repositories(repo_urls, root_folder):
    root_folder_path = Path(root_folder)
    root_folder_path.mkdir(parents=True, exist_ok=True)

    for url in tqdm(repo_urls, desc='Cloning repositories', unit='repo'):
        repo_name = Path(url).stem
        target_folder = root_folder_path / repo_name
        if not target_folder.exists():
            subprocess.run(['git', 'clone', url, str(target_folder)])
        else:
            tqdm.write(f'{target_folder} already exists, skipping cloning.')

if __name__ == '__main__':
    repository_list = [
        "https://github.com/jonmatthis/persepolis",
        "https://github.com/jonmatthis/SciHubEVA",
        "https://github.com/jonmatthis/PyQt-Fluent-Widgets",
        "https://github.com/jonmatthis/Furious",
        "https://github.com/jonmatthis/PyQtDarkTheme",
        "https://github.com/jonmatthis/QMaterialWidgets",
        "https://github.com/jonmatthis/Aura-Text",

    ]

    root_directory = Path().home() / "github_repos" /"jonmatthis" / "qt_resources"
    clone_repositories(repository_list, root_directory)