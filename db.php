<?php
/**
 * Data Storage & JSON Persistence Manager for Imvoi PHP Web App
 */

require_once __DIR__ . '/config.php';

function load_saved_customers() {
    $file = SAVED_CUSTOMERS_FILE;
    if (!file_exists($file)) {
        return [];
    }
    $content = file_get_contents($file);
    $data = json_decode($content, true);
    return is_array($data) ? $data : [];
}

function save_saved_customers($data) {
    $file = SAVED_CUSTOMERS_FILE;
    return file_put_contents($file, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)) !== false;
}

function get_invoice_counter() {
    $file = INVOICE_COUNTER_FILE;
    if (!file_exists($file)) {
        return ['last_number' => 747, 'prefix' => 'INV '];
    }
    $content = file_get_contents($file);
    $data = json_decode($content, true);
    if (!is_array($data)) {
        return ['last_number' => 747, 'prefix' => 'INV '];
    }
    return $data;
}

function save_invoice_counter($data) {
    $file = INVOICE_COUNTER_FILE;
    return file_put_contents($file, json_encode($data, JSON_PRETTY_PRINT)) !== false;
}

function get_next_invoice_no() {
    $counter = get_invoice_counter();
    $next_num = ($counter['last_number'] ?? 747) + 1;
    $prefix = $counter['prefix'] ?? 'INV ';
    return sprintf("%s%04d", $prefix, $next_num);
}

function increment_and_get_invoice_no() {
    $counter = get_invoice_counter();
    $counter['last_number'] = ($counter['last_number'] ?? 747) + 1;
    save_invoice_counter($counter);
    $prefix = $counter['prefix'] ?? 'INV ';
    return sprintf("%s%04d", $prefix, $counter['last_number']);
}

function get_invoice_by_no($receipt_no) {
    $customers = load_saved_customers();
    foreach ($customers as $index => $item) {
        $r_no = $item['group_data']['receipt_no'] ?? ($item['customer']['receipt_no'] ?? '');
        if (trim(strtolower($r_no)) === trim(strtolower($receipt_no))) {
            $item['_index'] = $index;
            return $item;
        }
    }
    return null;
}

function delete_invoice_by_no($receipt_no) {
    $customers = load_saved_customers();
    $filtered = [];
    $found = false;
    foreach ($customers as $item) {
        $r_no = $item['group_data']['receipt_no'] ?? ($item['customer']['receipt_no'] ?? '');
        if (trim(strtolower($r_no)) === trim(strtolower($receipt_no))) {
            $found = true;
            continue;
        }
        $filtered[] = $item;
    }
    if ($found) {
        save_saved_customers($filtered);
    }
    return $found;
}

function update_invoice_payment_status($receipt_no, $status) {
    $customers = load_saved_customers();
    $found = false;
    foreach ($customers as &$item) {
        $r_no = $item['group_data']['receipt_no'] ?? ($item['customer']['receipt_no'] ?? '');
        if (trim(strtolower($r_no)) === trim(strtolower($receipt_no))) {
            $item['payment_status'] = $status;
            if (isset($item['group_data'])) {
                $item['group_data']['payment_status'] = $status;
            }
            $found = true;
            break;
        }
    }
    if ($found) {
        save_saved_customers($customers);
    }
    return $found;
}

function add_or_update_invoice($invoice_data) {
    $customers = load_saved_customers();
    $target_no = $invoice_data['group_data']['receipt_no'] ?? ($invoice_data['customer']['receipt_no'] ?? '');
    
    $existing_index = -1;
    if (!empty($target_no)) {
        foreach ($customers as $idx => $item) {
            $r_no = $item['group_data']['receipt_no'] ?? ($item['customer']['receipt_no'] ?? '');
            if (!empty($r_no) && trim(strtolower($r_no)) === trim(strtolower($target_no))) {
                $existing_index = $idx;
                break;
            }
        }
    }

    if ($existing_index >= 0) {
        $customers[$existing_index] = $invoice_data;
    } else {
        // Prepend new invoice to top of list
        array_unshift($customers, $invoice_data);
    }

    return save_saved_customers($customers);
}

function delete_member_by_index($receipt_no, $m_idx) {
    $customers = load_saved_customers();
    $found = false;
    foreach ($customers as &$item) {
        $r_no = $item['group_data']['receipt_no'] ?? ($item['customer']['receipt_no'] ?? '');
        if (trim(strtolower($r_no)) === trim(strtolower($receipt_no))) {
            if (isset($item['members']) && is_array($item['members']) && isset($item['members'][$m_idx])) {
                array_splice($item['members'], $m_idx, 1);
                $exchangeRate = floatval($item['group_data']['exchange_rate'] ?? 33.90);
                $new_items = [];
                $grand_usd = 0.0;
                foreach ($item['members'] as $idx => $m) {
                    $name = $m['full_english_name'] ?? ($m['english_name'] ?? ($m['name'] ?? ''));
                    $vip = floatval($m['vip'] ?? 0);
                    $clearance = floatval($m['clearance_fee'] ?? 0);
                    $permit = floatval($m['work_permit'] ?? 0);
                    $car = floatval($m['car_fee'] ?? 0);
                    $visa = floatval($m['visa_fee'] ?? 0);
                    $evisa = floatval($m['e_visa'] ?? 0);
                    $row_usd = floatval($m['usd'] ?? 0);
                    if ($row_usd == 0 && ($vip || $clearance || $permit || $car || $visa || $evisa)) {
                        $row_usd = $vip + $clearance + $permit + $car + $visa + $evisa;
                    }
                    $grand_usd += $row_usd;
                    $new_items[] = [
                        'no' => $idx + 1,
                        'description' => $name,
                        'qty' => '1',
                        'e_visa' => $evisa > 0 ? ('$' . $evisa) : '',
                        'vip' => $vip > 0 ? ('$' . $vip) : '',
                        'overstay' => '',
                        'car_fee' => $car > 0 ? ('$' . $car) : '',
                        'visa' => $visa > 0 ? ('$' . $visa) : '',
                        'clearance_fee' => $clearance > 0 ? ('$' . $clearance) : '',
                        'work_permit' => $permit > 0 ? ('$' . $permit) : '',
                        'usd' => $row_usd
                    ];
                }
                $grand_thb = $grand_usd * $exchangeRate;
                $pax_count = count($item['members']);
                $first_cust_name = !empty($item['members']) ? ($item['members'][0]['full_english_name'] ?? 'N/A') : 'N/A';

                if (isset($item['group_info'])) {
                    $item['group_info']['customer_name'] = $first_cust_name;
                }
                if (isset($item['customer'])) {
                    $item['customer']['sex'] = "{$pax_count} Pax";
                }
                if (isset($item['group_data'])) {
                    $item['group_data']['items'] = $new_items;
                    $item['group_data']['totals'] = ['usd' => $grand_usd, 'baht' => $grand_thb];
                    $item['group_data']['group_customer_name'] = $first_cust_name;
                }
                $item['totals'] = ['usd' => $grand_usd, 'baht' => $grand_thb];
                $found = true;
                break;
            }
        }
    }
    if ($found) {
        save_saved_customers($customers);
    }
    return $found;
}
