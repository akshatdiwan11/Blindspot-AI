import { EmptyState, LinkButton } from "../components/ui";

export default function NotFound() {
  return <EmptyState title="Page not found" action={<LinkButton to="/overview">Go to overview</LinkButton>}>The page you opened does not exist.</EmptyState>;
}
