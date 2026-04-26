Run python -m pip install --upgrade pip setuptools
Requirement already satisfied: pip in /opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages (26.0.1)
Collecting setuptools
  Downloading setuptools-82.0.1-py3-none-any.whl.metadata (6.5 kB)
Downloading setuptools-82.0.1-py3-none-any.whl (1.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.0/1.0 MB 76.3 MB/s  0:00:00
Installing collected packages: setuptools
Successfully installed setuptools-82.0.1
Looking in indexes: 
Collecting torch==2.3.1
  Downloading  (190.4 MB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 190.4/190.4 MB 163.5 MB/s  0:00:01
Collecting filelock (from torch==2.3.1)
  Downloading filelock-3.25.2-py3-none-any.whl.metadata (2.0 kB)
Collecting typing-extensions>=4.8.0 (from torch==2.3.1)
  Downloading  (3.3 kB)
Collecting sympy (from torch==2.3.1)
  Downloading sympy-1.14.0-py3-none-any.whl.metadata (12 kB)
Collecting networkx (from torch==2.3.1)
  Downloading networkx-3.6.1-py3-none-any.whl.metadata (6.8 kB)
Collecting jinja2 (from torch==2.3.1)
  Downloading  (2.9 kB)
Collecting fsspec (from torch==2.3.1)
  Downloading fsspec-2026.2.0-py3-none-any.whl.metadata (10 kB)
Collecting MarkupSafe>=2.0 (from jinja2->torch==2.3.1)
  Downloading  (2.7 kB)
Collecting mpmath<1.4,>=1.1.0 (from sympy->torch==2.3.1)
  Downloading mpmath-1.3.0-py3-none-any.whl.metadata (8.6 kB)
Downloading  (44 kB)
Downloading filelock-3.25.2-py3-none-any.whl (26 kB)
Downloading fsspec-2026.2.0-py3-none-any.whl (202 kB)
Downloading  (134 kB)
Downloading  (22 kB)
Downloading networkx-3.6.1-py3-none-any.whl (2.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.1/2.1 MB 115.8 MB/s  0:00:00
Downloading sympy-1.14.0-py3-none-any.whl (6.3 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6.3/6.3 MB 199.0 MB/s  0:00:00
Downloading mpmath-1.3.0-py3-none-any.whl (536 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 536.2/536.2 kB 101.1 MB/s  0:00:00
Installing collected packages: mpmath, typing-extensions, sympy, networkx, MarkupSafe, fsspec, filelock, jinja2, torch

Successfully installed MarkupSafe-3.0.3 filelock-3.25.2 fsspec-2026.2.0 jinja2-3.1.6 mpmath-1.3.0 networkx-3.6.1 sympy-1.14.0 torch-2.3.1+cpu typing-extensions-4.15.0
Collecting setuptools==70.0.0 (from -r requirements.txt (line 15))
  Downloading setuptools-70.0.0-py3-none-any.whl.metadata (5.9 kB)
Collecting fastapi==0.111.1 (from -r requirements.txt (line 16))
  Downloading fastapi-0.111.1-py3-none-any.whl.metadata (26 kB)
Collecting uvicorn==0.30.1 (from uvicorn[standard]==0.30.1->-r requirements.txt (line 17))
  Downloading uvicorn-0.30.1-py3-none-any.whl.metadata (6.3 kB)
Collecting python-multipart==0.0.9 (from -r requirements.txt (line 18))
  Downloading python_multipart-0.0.9-py3-none-any.whl.metadata (2.5 kB)
Collecting websockets==12.0 (from -r requirements.txt (line 19))
  Downloading websockets-12.0-cp312-cp312-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
Collecting pydantic==2.7.4 (from -r requirements.txt (line 25))
  Downloading pydantic-2.7.4-py3-none-any.whl.metadata (109 kB)
Collecting pydantic-settings==2.3.4 (from -r requirements.txt (line 26))
  Downloading pydantic_settings-2.3.4-py3-none-any.whl.metadata (3.3 kB)
Collecting python-dotenv==1.0.1 (from -r requirements.txt (line 27))
  Downloading python_dotenv-1.0.1-py3-none-any.whl.metadata (23 kB)
Collecting sqlalchemy==2.0.31 (from -r requirements.txt (line 33))
  Downloading SQLAlchemy-2.0.31-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (9.6 kB)
Collecting asyncpg==0.29.0 (from -r requirements.txt (line 34))
  Downloading asyncpg-0.29.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.4 kB)
Collecting alembic==1.13.1 (from -r requirements.txt (line 35))
  Downloading alembic-1.13.1-py3-none-any.whl.metadata (7.4 kB)
Collecting psycopg2-binary==2.9.9 (from -r requirements.txt (line 36))
  Downloading psycopg2_binary-2.9.9-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.4 kB)
Collecting redis==5.0.7 (from -r requirements.txt (line 42))
  Downloading redis-5.0.7-py3-none-any.whl.metadata (9.3 kB)
Collecting celery==5.4.0 (from -r requirements.txt (line 43))
  Downloading celery-5.4.0-py3-none-any.whl.metadata (21 kB)
Collecting python-jose==3.3.0 (from python-jose[cryptography]==3.3.0->-r requirements.txt (line 50))
  Downloading python_jose-3.3.0-py2.py3-none-any.whl.metadata (5.4 kB)
Collecting passlib==1.7.4 (from passlib[bcrypt]==1.7.4->-r requirements.txt (line 51))
  Downloading passlib-1.7.4-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting groq==0.9.0 (from -r requirements.txt (line 58))
  Downloading groq-0.9.0-py3-none-any.whl.metadata (13 kB)
Collecting google-generativeai==0.7.2 (from -r requirements.txt (line 59))
  Downloading google_generativeai-0.7.2-py3-none-any.whl.metadata (4.0 kB)
Collecting openai==1.35.7 (from -r requirements.txt (line 60))
  Downloading openai-1.35.7-py3-none-any.whl.metadata (21 kB)
Collecting httpx==0.27.0 (from -r requirements.txt (line 63))
  Downloading httpx-0.27.0-py3-none-any.whl.metadata (7.2 kB)
Collecting openai-whisper==20231117 (from -r requirements.txt (line 72))
  Downloading openai-whisper-20231117.tar.gz (798 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 798.6/798.6 kB 93.3 MB/s  0:00:00
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Getting requirements to build wheel: started
  Getting requirements to build wheel: finished with status 'error'
  error: subprocess-exited-with-error
  
  × Getting requirements to build wheel did not run successfully.
  │ exit code: 1
  ╰─> [20 lines of output]
      Traceback (most recent call last):
        File "/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 3