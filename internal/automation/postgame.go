package automation

import (
	"context"
	"log"
	"time"

	"github.com/levyvix/league-auto-accept/internal/lcu"
)

type postGameWorkflow struct {
	honorSkipped   bool
	honorSkippedAt time.Time
	playedAgain    bool
}

func (workflow *postGameWorkflow) reset() {
	*workflow = postGameWorkflow{}
}

func (workflow *postGameWorkflow) step(
	ctx context.Context,
	api lcu.API,
	phase string,
	now time.Time,
) string {
	var notice string
	if !workflow.honorSkipped {
		if err := api.Request(ctx, "POST", "lol-honor-v2/v1/skip-honor-vote", nil, nil); err != nil {
			notice = "Could not skip honor; retrying"
			log.Printf("Skip honor failed in %s: %v", phase, err)
		} else {
			workflow.honorSkipped = true
			workflow.honorSkippedAt = now
			log.Print("Honor vote skipped")
		}
	}

	// The client needs time to dismiss the ballot before Play Again is available.
	if workflow.honorSkipped && now.Sub(workflow.honorSkippedAt) < 2*time.Second {
		return notice
	}
	if !workflow.playedAgain {
		if err := api.Request(ctx, "POST", "lol-lobby/v2/play-again", nil, nil); err != nil {
			notice = "Could not return to lobby; retrying"
			log.Printf("Play Again failed in %s: %v", phase, err)
		} else {
			workflow.playedAgain = true
			log.Print("Play Again accepted")
		}
	}
	return notice
}
