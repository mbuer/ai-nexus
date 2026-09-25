#!/usr/bin/perl -w
use strict;

# AI Nexus vzdump hook.
# Runs a fresh logical PostgreSQL backup inside VM 104 immediately before
# Proxmox captures the VM. QEMU Guest Agent executes the command inside
# the guest; runuser switches from guest root to the rootless Podman user.

my $phase = shift;

if ($phase eq 'backup-start') {
    my $mode = shift;
    my $vmid = shift;

    exit(0) unless defined($vmid) && $vmid eq '104';

    my @cmd = (
        '/usr/sbin/qm', 'guest', 'exec', '104', '--',
        '/usr/sbin/runuser', '-u', 'mb', '--',
        '/bin/bash', '-lc',
        'cd /home/mb/projects/ai-nexus && make backup'
    );

    print "AI-NEXUS-HOOK: creating fresh Birdynator logical backup before VM 104 backup\n";

    system(@cmd) == 0
        or die "AI-NEXUS-HOOK: Birdynator logical backup failed; aborting VM backup\n";

    print "AI-NEXUS-HOOK: logical backup completed successfully\n";
}

exit(0);
