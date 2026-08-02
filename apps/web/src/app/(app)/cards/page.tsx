import { redirect } from "next/navigation";

// /cards has no page of its own now that "Your cards" folded into Portfolio.
// Portfolio is the natural landing tab: it answers "what do I hold and is it
// working for me" before Explore or Recommendations ask "what else".
export default function CardsIndex() {
  redirect("/cards/portfolio");
}
