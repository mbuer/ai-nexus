#!/usr/bin/perl -w
use strict;

# AI Nexus vzdump hook template.
# Customize these values in the installed Proxmox copy. Keep live environment
# identifiers out of the public repository.
my $AI_NEXUS_VMID = 'REPLACE_WITH_VMID';
my $AI_NEXUS_USER = 'REPLACE_WITH_ADMIN_USER';
my $AI_NEXUS_REPO = '/path/to/ai-nexus';

my $phase = shift;

if ($phase eq 'backup-start') {
    my $mode = shift;
    my $vmid = shift;

    exit(0) unless defined($vmid) && $vmid eq $AI_NEXUS_VMID;

    my @cmd = (
        '/usr/sbin/qm', 'guest', 'exec', $AI_NEXUS_VMID, '--',
        '/usr/sbin/runuser', '-u', $AI_NEXUS_USER, '--',
        '/bin/bash', '-lc',
        "cd '$AI_NEXUS_REPO' && make backup"
    );

    print "AI-NEXUS-HOOK: creating fresh Birdynator logical backup before VM backup\n";

    system(@cmd) == 0
        or die "AI-NEXUS-HOOK: Birdynator logical backup failed; aborting VM backup\n";

    print "AI-NEXUS-HOOK: logical backup completed successfully\n";
}

exit(0);
