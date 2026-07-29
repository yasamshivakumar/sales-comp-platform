import { Skeleton, Stack, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";

export default function TableSkeleton({ rows = 6, columns = 5 }) {
  return (
    <Table className="ent-table-skel" aria-hidden>
      <TableHead>
        <TableRow>
          {Array.from({ length: columns }).map((_, i) => (
            <TableCell key={i}>
              <Skeleton width="60%" />
            </TableCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {Array.from({ length: rows }).map((_, r) => (
          <TableRow key={r}>
            {Array.from({ length: columns }).map((_, c) => (
              <TableCell key={c}>
                <Skeleton width={`${55 + ((r + c) % 4) * 10}%`} />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function CardSkeleton({ count = 4 }) {
  return (
    <Stack direction="row" spacing={1.5} className="ent-kpi-grid" useFlexGap flexWrap="wrap">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} variant="rounded" height={110} sx={{ flex: "1 1 160px", borderRadius: 2 }} />
      ))}
    </Stack>
  );
}
