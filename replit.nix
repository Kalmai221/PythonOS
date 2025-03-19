{pkgs}: {
  deps = [
    pkgs.nodePackages.prettier
    pkgs.unixtools.ping
    pkgs.nano
  ];
}
