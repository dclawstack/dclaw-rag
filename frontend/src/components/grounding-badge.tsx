import { Badge } from "@/components/ui/badge";
import { ShieldCheck, ShieldAlert, ShieldX, HelpCircle } from "lucide-react";

interface Props {
  abstained?: boolean;
  faithfulness?: "grounded" | "partial" | "unsupported" | null;
}

/** Shows how well the answer is grounded in the retrieved sources. */
export function GroundingBadge({ abstained, faithfulness }: Props) {
  if (abstained) {
    return (
      <Badge variant="outline" className="gap-1 border-amber-400 text-amber-600">
        <HelpCircle className="h-3 w-3" />
        Not enough info
      </Badge>
    );
  }
  if (faithfulness === "grounded") {
    return (
      <Badge className="gap-1 bg-emerald-500 text-white hover:bg-emerald-500">
        <ShieldCheck className="h-3 w-3" />
        Grounded
      </Badge>
    );
  }
  if (faithfulness === "partial") {
    return (
      <Badge variant="outline" className="gap-1 border-amber-400 text-amber-600">
        <ShieldAlert className="h-3 w-3" />
        Partially supported
      </Badge>
    );
  }
  if (faithfulness === "unsupported") {
    return (
      <Badge variant="destructive" className="gap-1">
        <ShieldX className="h-3 w-3" />
        Unsupported
      </Badge>
    );
  }
  return null;
}
