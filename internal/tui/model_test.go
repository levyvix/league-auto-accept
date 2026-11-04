package tui

import (
	tea "charm.land/bubbletea/v2"
	"context"
	"github.com/levyvix/league-auto-accept/internal/config"
	"strings"
	"testing"
)

func TestSettingsAndPicker(t *testing.T) {
	s := config.Defaults()
	s.AutoSave = false
	m := New(context.Background(), s, "unused")
	m.screen = "settings"
	next, _ := m.Update(tea.KeyPressMsg{Code: 'p', Text: "p"})
	m = next.(Model)
	if m.Settings.AutoPick {
		t.Fatal("pick toggle")
	}
	m.screen = "picker"
	m.champions = []Champion{{ID: 90, Name: "Malzahar"}, {ID: 22, Name: "Ashe"}}
	m.input.SetValue("mal")
	if len(m.filtered()) != 2 {
		t.Fatal(m.filtered())
	}
	if !strings.Contains(m.View().Content, "Malzahar") {
		t.Fatal("missing filtered champion")
	}
}

func TestInventoryDuplicatesAreCollapsed(t *testing.T) {
	got := uniqueChampions([]Champion{
		{ID: 10090, Name: "Malzahar"}, {ID: 90, Name: "Malzahar"},
		{ID: 90, Name: "Malzahar"}, {ID: 10091, Name: " malzahar "},
		{ID: 22, Name: "Ashe"}, {ID: 22, Name: "Ashe variant"},
		{ID: 0, Name: "None"}, {ID: -1, Name: ""},
	})
	if len(got) != 2 || got[0].Name != "Ashe" || got[1].ID != 90 {
		t.Fatalf("expected unique base champions, got %+v", got)
	}
	m := New(context.Background(), config.Defaults(), "unused")
	m.champions = got
	for _, slot := range []int{0, 4} {
		m.slot = slot
		if len(m.filtered()) != 3 {
			t.Fatalf("slot %d: %+v", slot, m.filtered())
		}
	}
}
