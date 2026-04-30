Run python -m pip install --upgrade pip setuptools wheel
Requirement already satisfied: pip in /opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages (26.0.1)
Collecting setuptools
  Downloading setuptools-82.0.1-py3-none-any.whl.metadata (6.5 kB)
Collecting wheel
  Downloading wheel-0.47.0-py3-none-any.whl.metadata (2.3 kB)
Collecting packaging>=24.0 (from wheel)
  Downloading packaging-26.2-py3-none-any.whl.metadata (3.5 kB)
Downloading setuptools-82.0.1-py3-none-any.whl (1.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.0/1.0 MB 73.9 MB/s  0:00:00
Downloading wheel-0.47.0-py3-none-any.whl (32 kB)
Downloading packaging-26.2-py3-none-any.whl (100 kB)
Installing collected packages: setuptools, packaging, wheel

Successfully installed packaging-26.2 setuptools-82.0.1 wheel-0.47.0
Looking in indexes: https://download.pytorch.org/whl/cpu
Collecting torch==2.3.1
  Downloading https://download-r2.pytorch.org/whl/cpu/torch-2.3.1%2Bcpu-cp312-cp312-linux_x86_64.whl (190.4 MB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 190.4/190.4 MB 105.5 MB/s  0:00:01
Collecting filelock (from torch==2.3.1)
  Downloading filelock-3.25.2-py3-none-any.whl.metadata (2.0 kB)
Collecting typing-extensions>=4.8.0 (from torch==2.3.1)
  Downloading https://download.pytorch.org/whl/typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
Collecting sympy (from torch==2.3.1)
  Downloading sympy-1.14.0-py3-none-any.whl.metadata (12 kB)
Collecting networkx (from torch==2.3.1)
  Downloading networkx-3.6.1-py3-none-any.whl.metadata (6.8 kB)
Collecting jinja2 (from torch==2.3.1)
  Downloading https://download.pytorch.org/whl/jinja2-3.1.6-py3-none-any.whl.metadata (2.9 kB)
Collecting fsspec (from torch==2.3.1)
  Downloading fsspec-2026.2.0-py3-none-any.whl.metadata (10 kB)
Collecting MarkupSafe>=2.0 (from jinja2->torch==2.3.1)
  Downloading https://download.pytorch.org/whl/markupsafe-3.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.7 kB)
Collecting mpmath<1.4,>=1.1.0 (from sympy->torch==2.3.1)
  Downloading mpmath-1.3.0-py3-none-any.whl.metadata (8.6 kB)
Downloading https://download.pytorch.org/whl/typing_extensions-4.15.0-py3-none-any.whl (44 kB)
Downloading filelock-3.25.2-py3-none-any.whl (26 kB)
Downloading fsspec-2026.2.0-py3-none-any.whl (202 kB)
Downloading https://download.pytorch.org/whl/jinja2-3.1.6-py3-none-any.whl (134 kB)
Downloading https://download.pytorch.org/whl/markupsafe-3.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (22 kB)
Downloading networkx-3.6.1-py3-none-any.whl (2.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.1/2.1 MB 163.0 MB/s  0:00:00
Downloading sympy-1.14.0-py3-none-any.whl (6.3 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6.3/6.3 MB 278.4 MB/s  0:00:00
Downloading mpmath-1.3.0-py3-none-any.whl (536 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 536.2/536.2 kB 94.5 MB/s  0:00:00
Installing collected packages: mpmath, typing-extensions, sympy, networkx, MarkupSafe, fsspec, filelock, jinja2, torch

Successfully installed MarkupSafe-3.0.3 filelock-3.25.2 fsspec-2026.2.0 jinja2-3.1.6 mpmath-1.3.0 networkx-3.6.1 sympy-1.14.0 torch-2.3.1+cpu typing-extensions-4.15.0
Collecting git+https://github.com/openai/whisper.git@v20240930
  Cloning https://github.com/openai/whisper.git (to revision v20240930) to /tmp/pip-req-build-t5l9u8e9
  Running command git clone --filter=blob:none --quiet https://github.com/openai/whisper.git /tmp/pip-req-build-t5l9u8e9
  Running command git checkout -q 25639fc17ddc013d56c594bfbf7644f2185fad84
  Resolved https://github.com/openai/whisper.git to commit 25639fc17ddc013d56c594bfbf7644f2185fad84
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'error'
  error: subprocess-exited-with-error
  
  × Getting requirements to build wheel did not run successfully.
  │ exit code: 1
  ╰─> [20 lines of output]
      Traceback (most recent call last):
        File "/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 389, in <module>
          main()
        File "/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 373, in main
          json_out["return_val"] = hook(**hook_input["kwargs"])
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 143, in get_requires_for_build_wheel
          return hook(config_settings)
                 ^^^^^^^^^^^^^^^^^^^^^
        File "/tmp/pip-build-env-m2_x_cdj/overlay/lib/python3.12/site-packages/setuptools/build_meta.py", line 333, in get_requires_for_build_wheel
          return self._get_build_requires(config_settings, requirements=[])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/tmp/pip-build-env-m2_x_cdj/overlay/lib/python3.12/site-packages/setuptools/build_meta.py", line 301, in _get_build_requires
          self.run_setup()
        File "/tmp/pip-build-env-m2_x_cdj/overlay/lib/python3.12/site-packages/setuptools/build_meta.py", line 520, in run_setup
          super().run_setup(setup_script=setup_script)
        File "/tmp/pip-build-env-m2_x_cdj/overlay/lib/python3.12/site-packages/setuptools/build_meta.py", line 317, in run_setup
          exec(code, locals())
        File "<string>", line 5, in <module>
      ModuleNotFoundError: No module named 'pkg_resources'
      [end of output]
  
  note: This error originates from a subprocess, and is likely not a problem with pip.
ERROR: Failed to build 'git+https://github.com/openai/whisper.git@v20240930' when getting requirements to build wheel