import os
import site

site.USER_SITE = None
site.USER_BASE = None
site.ENABLE_USER_SIZE = None

site.addsitedir(os.path.join(os.path.dirname(__file__), 'site-packages'))
