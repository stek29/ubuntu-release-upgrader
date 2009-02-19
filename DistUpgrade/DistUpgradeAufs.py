
import logging
import os
import os.path
import subprocess

def _bindMount(from_dir, to_dir):
    " helper that bind mounts a given dir to a new place "
    if not os.path.exists(to_dir):
        os.makedirs(to_dir)
    cmd = ["mount","--bind", from_dir, to_dir]
    res = subprocess.call(cmd)
    if res != 0:
        # FIXME: revert already mounted stuff
        logging.error("Failed to bind mount from '%s' to '%s'" % (from_dir, to_dir))
        return False
    return True

def _aufsOverlayMount(target, rw_dir):
    """ 
    helper that takes a target dir and mounts a rw dir over it, e.g.
    /var , /tmp/upgrade-rw
    """
    if not os.path.exists(rw_dir+target):
        os.makedirs(rw_dir+target)
    cmd = ["mount",
           "-t","aufs",
           "-o","br:%s:%s=ro" % (rw_dir+target, target),
           "none",
           target]
    res = subprocess.call(cmd)
    if res != 0:
        # FIXME: revert already mounted stuff
        logging.error("Failed to mount rw aufs overlay for '%s'" % target)
        return False
    return True

def is_aufs_mount(dir):
    " test if the given dir is already mounted with aufs overlay "
    for line in open("/proc/mounts"):
        (device, mountpoint, fstype, options, a, b) = line.split()
        if device == "none" and fstype == "aufs" and mountpoint == dir:
            return True
    return False

def is_submount(mountpoint, systemdirs):
    " helper: check if the given mountpoint is a submount of a systemdir "
    for d in systemdirs:
        if mountpoint.startswith(d):
            return True
    return False

def is_real_fs(fs):
    if fs.startswith("fuse"):
        return False
    if fs in ["rootfs","tmpfs","proc","fusectrl","aufs",
              "devpts","binfmt_misc", "sysfs"]:
        return False
    return True

def setupAufs(rw_dir):
    " setup aufs overlay over the rootfs "
    
    # FIXME: * this is currently run *after* /var/log/dist-upgrade/main.log
    #          is opened and its not in the aufs file    
    #        * we need to find a way to tell all the existing daemon 
    #          to look into the new namespace. so probably something
    #          like a reboot is required and some hackery in initramfs-tools
    #          to ensure that we boot into a overlay ready system
    logging.debug("setupAufs")
    if not os.path.exists("/proc/mounts"):
        logging.debug("no /proc/mounts, can not do aufs overlay")
        return False
    systemdirs = ["/bin","/boot","/etc","/lib","/sbin","/usr","/var"]

    # verify that there are no submounts of a systemdir and collect
    # the stuff that needs bind mounting (because a aufs does not
    # include sub mounts)
    needs_bind_mount = set()
    for line in open("/proc/mounts"):
        (device, mountpoint, fstype, options, a, b) = line.split()
        if is_real_fs(fstype) and is_submount(mountpoint, systemdirs):
            logging.warning("mountpoint %s submount of systemdir" % mountpoint)
            return False
        if (fstype != "aufs" and not is_real_fs(fstype) and is_submount(mountpoint, systemdirs)):
            logging.debug("found %s that needs bind mount", mountpoint)
            needs_bind_mount.add(mountpoint)

    # aufs mounts do not support stacked filesystems, so
    # if we mount /var we will loose the tmpfs stuff
    # first bind mount varun and varlock into the tmpfs
    for d in needs_bind_mount:
        if not _bindMount(d, rw_dir+"/needs_bind_mount/"+d):
            return False
    # setup writable overlay into /tmp/upgrade-rw so that all 
    # changes are written there instead of the real fs
    for d in systemdirs:
        if not is_aufs_mount(d):
            if not _aufsOverlayMount(d, rw_dir):
                return False
    # now bind back the tempfs to the original location
    for d in needs_bind_mount:
        if not _bindMount(rw_dir+"/needs_bind_mount/"+d, d):
            return False
        
    # FIXME: now what we *could* do to apply the changes is to
    #        mount -o bind / /orig 
    #        (bind is important, *not* rbind that includes submounts)
    # 
    #        This will give us the original "/" without the 
    #        aufs rw overlay  - *BUT* only if "/" is all on one parition
    #             
    #        then apply the diff (including the whiteouts) to /orig
    #        e.g. by "rsync -av /tmp/upgrade-rw /orig"
    #                "script that search for whiteouts and removes them"
    #        (whiteout files start with .wh.$name
    #         whiteout dirs with .wh..? - check with aufs man page)
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print setupAufs("/tmp/upgrade-rw")
