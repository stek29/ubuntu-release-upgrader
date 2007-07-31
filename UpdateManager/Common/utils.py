from gettext import gettext as _
import locale
import os

def country_mirror():
  # special cases go here
  lang_mirror = { 'C'     : '',
                }
  # no lang, no mirror
  if not os.environ.has_key('LANG'):
    return ''
  lang = os.environ['LANG']
  # check if it is a special case
  if lang_mirror.has_key(lang[:5]):
    return lang_mirror[lang[:5]]
  # now check for the most comon form (en_US.UTF-8)
  if "_" in lang:
    country = lang.split(".")[0].split("_")[1]
    return country+"."
  else:
    return lang[:2]+"."
  return ''

def str_to_bool(str):
  if str == "0" or str.upper() == "FALSE":
    return False
  return True

def utf8(str):
  return unicode(str, 'latin1').encode('utf-8')

def error(parent, summary, message):
  import gtk
  d = gtk.MessageDialog(parent=parent,
                        flags=gtk.DIALOG_MODAL,
                        type=gtk.MESSAGE_ERROR,
                        buttons=gtk.BUTTONS_CLOSE)
  d.set_markup("<big><b>%s</b></big>\n\n%s" % (summary, message))
  d.realize()
  d.window.set_functions(gtk.gdk.FUNC_MOVE)
  d.set_title("")
  res = d.run()
  d.destroy()
  return False

def humanize_size(bytes):
    """
    Convert a given size in bytes to a nicer better readable unit
    """
    if bytes == 0:
        # TRANSLATORS: download size is 0
        return _("None")
    elif bytes < 1024:
        # TRANSLATORS: download size of very small updates
        return _("1 KB")
    elif bytes < 1024 * 1024:
        # TRANSLATORS: download size of small updates, e.g. "250 KB"
        return locale.format(_("%.0f KB"), bytes/1024)
    else:
        # TRANSLATORS: download size of updates, e.g. "2.3 MB"
        return locale.format(_("%.1f MB"), bytes / 1024 / 1024)
