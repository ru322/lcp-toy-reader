{
  description = "lcp-toy-reader dev environment (EDRLab LCP server v2: lcpencrypt / lcpserver)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        lcp-server = pkgs.buildGoModule rec {
          pname = "lcp-server";
          version = "2.0.0";

          src = pkgs.fetchFromGitHub {
            owner = "edrlab";
            repo = "lcp-server";
            rev = "v${version}";
            hash = "sha256-07ecOvp2Ni8VkzLz73mZLFPJzEHbrGWoopFZ8ttcqK8=";
          };

          vendorHash = "sha256-WewCSN/D6/FjWgm1U2hNqFUjGQ/ef3nbVY7DYHgk4/M=";

          subPackages = [
            "cmd/lcpencrypt"
            "cmd/lcpserver"
            "cmd/lcpchecker"
          ];

          # sqlite ドライバ (go-sqlite3) が cgo を使う
          env.CGO_ENABLED = 1;

          doCheck = false;

          meta = {
            description = "EDRLab LCP server v2 (lcpencrypt, lcpserver, lcpchecker)";
            homepage = "https://github.com/edrlab/lcp-server";
            license = pkgs.lib.licenses.bsd3;
          };
        };
      in
      {
        packages = {
          inherit lcp-server;
          default = lcp-server;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            lcp-server
            pkgs.sqlite
            pkgs.zip
            pkgs.jq
          ];
        };
      }
    );
}
