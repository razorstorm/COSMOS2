import subprocess as sp
import os
import re

def run(cmd):
    sp.check_output(cmd, shell=True)


def find_all(path, reg_expr, inverse=False, remove_prefix=False):
    if not path.endswith('/'):
        path = path + '/'
    for root, dirnames, filenames in os.walk(path):
        for filename in filenames:
            match = re.search(reg_expr, filename) is not None
            if inverse:
                match = not match
            if match:
                out = os.path.join(root, filename)
                if remove_prefix:
                    out = out.replace(path, '')
                yield out


def main():
    if os.path.exists('cosmos_py2'):
        run('rm -rf cosmos_py2')

    run('cp -r cosmos cosmos_py2')
    run('3to2 -n -w --no-diffs -j 6 cosmos_py2')
    # run('python setup.py sdist upload')

        # run('curl http://readthedocs.org/build/cosmos-wfm')


if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser()
    # p.add_argument('new_version')
    args = p.parse_args()

    main(**vars(args))
