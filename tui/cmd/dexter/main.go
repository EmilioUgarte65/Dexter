package main

import (
	"fmt"
	"os"

	"github.com/gentleman-programming/dexter/internal/app"
)

// version is set by GoReleaser via ldflags at build time.
var version = "dev"

func main() {
	app.Version = version

	if err := app.Run(os.Args); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
