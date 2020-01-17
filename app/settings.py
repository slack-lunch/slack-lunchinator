import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = False

try:
    SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
except KeyError:
    if DEBUG:
        SECRET_KEY = 'vz!!phb8mzj)$%&ax6=w%1&=cfu7_=u^z+jker5=bei$o)q93j'  # only for testing
    else:
        raise Exception("Set DJANGO_SECRET_KEY environment variable or use DEBUG=true in settings.py.")

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'jet',

    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',

    'lunchinator'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

WSGI_APPLICATION = 'app.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

UTH_USER_MODEL = 'lunchinator.User'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

URL_PREFIX = os.getenv('URL_PREFIX', default='.')
STATIC_URL = f'/{URL_PREFIX}/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
