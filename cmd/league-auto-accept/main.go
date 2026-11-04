package main

import (
	tea "charm.land/bubbletea/v2"
	"context"
	"fmt"
	"github.com/levyvix/league-auto-accept/internal/config"
	"github.com/levyvix/league-auto-accept/internal/tui"
	"log"
	"os"
)

func main() {
	f, err := os.OpenFile("league_auto_accept.log", os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer f.Close()
	log.SetOutput(f)
	path, err := config.Path()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return
	}
	s, err := config.Load(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Cannot load settings:", err)
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	p := tea.NewProgram(tui.New(ctx, s, path))
	final, err := p.Run()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return
	}
	if model, ok := final.(tui.Model); ok {
		if err := config.Save(path, model.Settings); err != nil {
			fmt.Fprintln(os.Stderr, err)
		}
	}
}
