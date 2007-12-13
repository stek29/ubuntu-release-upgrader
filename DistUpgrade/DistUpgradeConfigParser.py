from ConfigParser import ConfigParser, NoOptionError, NoSectionError
import subprocess
import os.path

class DistUpgradeConfig(ConfigParser):
    def __init__(self, datadir, name="DistUpgrade.cfg"):
        ConfigParser.__init__(self)
        # we support a config overwrite, if DistUpgrade.cfg.dapper exists
        # and the user runs dapper, that one will be used
        from_release = subprocess.Popen(["lsb_release","-c","-s"],
                                        stdout=subprocess.PIPE).communicate()[0].strip()
        self.datadir=datadir
        if os.path.exists(name+"."+from_release):
            name = name+"."+from_release
        self.read(os.path.join(datadir,name))
    def getWithDefault(self, section, option, default):
        try:
            return self.get(section, option)
        except (NoSectionError, NoOptionError),e:
            return default
    def getlist(self, section, option):
        try:
            tmp = self.get(section, option)
        except (NoSectionError,NoOptionError),e:
            return []
        items = [x.strip() for x in tmp.split(",")]
        return items
    def getListFromFile(self, section, option):
        try:
            filename = self.get(section, option)
        except NoOptionError:
            return []
        items = [x.strip() for x in open(self.datadir+"/"+filename)]
        return filter(lambda s: not s.startswith("#") and not s == "", items)


if __name__ == "__main__":
    c = DistUpgradeConfig()
    print c.getlist("Distro","MetaPkgs")
    print c.getlist("Distro","ForcedPurges")
    print c.getListFromFile("Sources","ValidMirrors")
