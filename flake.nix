{
  description = "Hugo-powered website environment for the EMI research group";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        hugoPkg = pkgs.hugo; # extended build with SCSS support
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          requests
        ]);
      in {
        packages = {
          hugo = hugoPkg;
          default = hugoPkg;
        };

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            hugo
            nodejs_20
            git
            python3
            pythonEnv
          ];
          shellHook = ''
            echo "Hugo ${hugoPkg.version} ready. Run 'hugo server -D' to start the local site."
            echo "Python ${pkgs.python3.version} with requests package available for fetching publications."
            echo "Run 'python scripts/fetch_publications.py' to fetch publications from ORCID."
          '';
        };
      }
    );
}
