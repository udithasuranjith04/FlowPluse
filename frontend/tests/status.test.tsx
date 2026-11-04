import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ModeBadge } from "../src/App";
import { duration, title } from "../src/api";

describe("honest source labels", () => {
  it("labels replay and updates to offline without claiming live", () => {
    const { rerender } = render(<ModeBadge mode="REPLAY" synthetic />);
    expect(screen.getByText("REPLAY DEMO")).toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
    rerender(<ModeBadge mode="OFFLINE" />);
    expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    expect(screen.queryByText("REPLAY DEMO")).not.toBeInTheDocument();
  });
  it("distinguishes real replay, snapshots and live video from the generated demo", () => {
    const { rerender } = render(<ModeBadge mode="REPLAY" />);
    expect(screen.getByText("REPLAY")).toBeInTheDocument();
    expect(screen.queryByText("REPLAY DEMO")).not.toBeInTheDocument();
    rerender(<ModeBadge mode="SNAPSHOT" />);
    expect(screen.getByText("SNAPSHOT")).toBeInTheDocument();
    rerender(<ModeBadge mode="LIVE" />);
    expect(screen.getByText("VERIFYING VIDEO")).toBeInTheDocument();
    rerender(<ModeBadge mode="LIVE" continuousVerified />);
    expect(screen.getByText("CONTINUOUS VIDEO")).toBeInTheDocument();
    rerender(<ModeBadge mode="PAUSED" />);
    expect(screen.getByText("PAUSED")).toBeInTheDocument();
  });
  it("uses qualified observation language and measured duration formatting", () => {
    expect(title("potential_stopped_vehicle")).toBe(
      "Potential stopped vehicle",
    );
    expect(title("congestion_buildup")).toBe("Congestion buildup");
    expect(duration(125)).toBe("2m 5s");
  });
});
