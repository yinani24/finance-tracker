import { redirect } from "next/navigation";

// /cards has no page of its own now that "Your cards" folded into Portfolio.
// It lands on Recommendations: after dropping a statement, "which card should
// I get" is the question being asked, not "what do I already have".
export default function CardsIndex() {
  redirect("/cards/recommendations");
}
